import mimetypes
import re
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from prospects.propify_auth import (
    WEB_PROFILE_SESSION_KEY,
    WEB_TOKEN_SESSION_KEY,
    PropifyAuthError,
    authenticate_propify_credentials,
    clear_web_propify_session,
    get_web_propify_principal,
)

from .forms import AttachmentForm, DocumentTypeForm, ExternalAgentForm
from .models import DocumentType, ExternalAgent, ExternalAgentAttachment


MAX_ATTACHMENTS_PER_SUBMISSION = 20
INITIAL_ATTACHMENT_ROWS = 6


def _username(request):
    principal = getattr(request, 'propify_user', None)
    return str(getattr(principal, 'username', '') or '').strip()


def _safe_next(request, default='/agentes-externos/'):
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def _empty_attachment_forms():
    return [
        AttachmentForm(prefix=f'doc_{index}')
        for index in range(INITIAL_ATTACHMENT_ROWS)
    ]


def _attachment_forms_from_request(request):
    if request.method != 'POST':
        return _empty_attachment_forms(), ''

    indices = sorted({
        int(match.group(1))
        for key in [*request.POST.keys(), *request.FILES.keys()]
        if (match := re.fullmatch(r'doc_(\d+)-(?:document_type|file)', key))
    })
    if len(indices) > MAX_ATTACHMENTS_PER_SUBMISSION:
        return [], (
            f'Puedes subir como máximo {MAX_ATTACHMENTS_PER_SUBMISSION} '
            'documentos por operación.'
        )
    if indices:
        forms = []
        for index in indices:
            prefix = f'doc_{index}'
            document_type = request.POST.get(f'{prefix}-document_type')
            uploaded = request.FILES.get(f'{prefix}-file')
            if not document_type and not uploaded:
                continue
            forms.append(AttachmentForm(
                data=request.POST,
                files=request.FILES,
                prefix=prefix,
            ))
        return forms, ''

    # Backward-compatible single attachment payload.
    document_types = request.POST.getlist('document_type')
    uploaded_files = request.FILES.getlist('file')
    count = max(len(document_types), len(uploaded_files))
    if count > MAX_ATTACHMENTS_PER_SUBMISSION:
        return [], (
            f'Puedes subir como máximo {MAX_ATTACHMENTS_PER_SUBMISSION} '
            'documentos por operación.'
        )
    forms = []
    for index in range(count):
        document_type = document_types[index] if index < len(document_types) else ''
        uploaded = uploaded_files[index] if index < len(uploaded_files) else None
        if not document_type and not uploaded:
            continue
        forms.append(AttachmentForm(
            data={'document_type': document_type},
            files={'file': uploaded} if uploaded else None,
        ))
    return forms, ''


def _save_attachment_forms(request, agent, forms):
    saved = 0
    for form in forms:
        if not form.is_valid():
            continue
        attachment = form.save(commit=False)
        attachment.agent = agent
        attachment.original_name = getattr(form, 'original_name', '')
        attachment.uploaded_by_username = _username(request)
        try:
            attachment.save()
        except Exception:
            messages.error(
                request,
                'Uno de los documentos no pudo subirse a Azure. '
                'Puedes intentarlo nuevamente desde la ficha.',
            )
            continue
        saved += 1
    if saved:
        suffix = 's' if saved != 1 else ''
        messages.success(
            request,
            f'{saved} documento{suffix} adjunto{suffix} '
            f'guardado{suffix} en Azure.',
        )
    return saved


def external_agent_access_required(view_func):
    """Exige una sesión web de Propify, sin pedir el login interno del ACM."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        principal = get_web_propify_principal(request)
        if principal is None:
            query = urlencode({'next': request.get_full_path()})
            return redirect(f'/agentes-externos/login/?{query}')
        request.propify_user = principal
        return view_func(request, *args, **kwargs)

    return wrapped


def login_view(request):
    if request.method == 'GET' and get_web_propify_principal(request) is not None:
        return redirect(_safe_next(request))

    error = ''
    username = ''
    next_url = _safe_next(request)
    if request.method == 'POST':
        username = str(request.POST.get('username') or '').strip()
        password = str(request.POST.get('password') or '')
        if not username or not password:
            error = 'Usuario y contraseña son obligatorios.'
        else:
            try:
                _, principal = authenticate_propify_credentials(username, password)
            except PropifyAuthError as exc:
                error = str(exc)
            else:
                request.session[WEB_TOKEN_SESSION_KEY] = principal.token
                request.session[WEB_PROFILE_SESSION_KEY] = principal.profile
                request.session.set_expiry(60 * 60 * 24 * 30)
                return redirect(next_url)

    return render(request, 'external_agents/login.html', {
        'error': error,
        'username': username,
        'next': next_url,
    })


def logout_view(request):
    clear_web_propify_session(request)
    return redirect('external_agents:login')


@external_agent_access_required
def dashboard(request):
    query = str(request.GET.get('q') or '').strip()
    status = str(request.GET.get('estado') or '').strip()
    document_type = str(request.GET.get('tipo_documento') or '').strip()
    level = str(request.GET.get('nivel') or '').strip()
    agents = ExternalAgent.objects.annotate(attachment_count=Count('attachments'))

    if query:
        agents = agents.filter(
            Q(full_name__icontains=query)
            | Q(document_number__icontains=query)
            | Q(email__icontains=query)
            | Q(mobile__icontains=query)
            | Q(observations__icontains=query)
        )
    if status == 'activos':
        agents = agents.filter(is_active=True)
    elif status == 'inactivos':
        agents = agents.filter(is_active=False)
    if document_type.isdigit():
        agents = agents.filter(personal_document_type_id=int(document_type))
    if level in ExternalAgent.Level.values:
        agents = agents.filter(level=level)

    total_agents = ExternalAgent.objects.count()
    active_agents = ExternalAgent.objects.filter(is_active=True).count()
    with_attachments = ExternalAgent.objects.filter(attachments__isnull=False).distinct().count()
    without_attachments = ExternalAgent.objects.filter(
        attachments__isnull=True,
    ).count()

    paginator = Paginator(
        agents.select_related('personal_document_type').order_by(
            'full_name',
            'pk',
        ),
        18,
    )
    page = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring.pop('q', None)
    return render(request, 'external_agents/dashboard.html', {
        'page': page,
        'agents': page.object_list,
        'query': query,
        'status_filter': status,
        'document_type_filter': document_type,
        'level_filter': level,
        'level_choices': ExternalAgent.Level.choices,
        'document_types': DocumentType.objects.filter(
            scope=DocumentType.Scope.PERSONAL,
            is_active=True,
        ).order_by('sort_order', 'name', 'pk'),
        'stats': {
            'total': total_agents,
            'active': active_agents,
            'with_attachments': with_attachments,
            'without_attachments': without_attachments,
        },
        'pagination_query': querystring.urlencode(),
    })


@external_agent_access_required
def agent_create(request):
    form = ExternalAgentForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
    )
    attachment_forms, attachment_error = _attachment_forms_from_request(request)
    agent_valid = form.is_valid()
    attachments_valid = not attachment_error and all(
        attachment_form.is_valid() for attachment_form in attachment_forms
    )
    if request.method == 'POST' and agent_valid and attachments_valid:
        agent = form.save(commit=False)
        agent.created_by_username = _username(request)
        agent.updated_by_username = agent.created_by_username
        agent.save()
        _save_attachment_forms(request, agent, attachment_forms)
        messages.success(request, 'Agente externo registrado correctamente.')
        return redirect('external_agents:agent_detail', pk=agent.pk)
    return render(request, 'external_agents/agent_form.html', {
        'form': form,
        'mode': 'create',
        'agent': None,
        'attachment_forms': attachment_forms,
        'empty_attachment_form': AttachmentForm(prefix='doc___index__'),
        'attachment_error': attachment_error,
        'attachment_types_available': (
            AttachmentForm().fields['document_type'].queryset.exists()
        ),
    })


@external_agent_access_required
def agent_edit(request, pk):
    agent = get_object_or_404(ExternalAgent, pk=pk)
    form = ExternalAgentForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        instance=agent,
    )
    attachment_forms, attachment_error = _attachment_forms_from_request(request)
    agent_valid = form.is_valid()
    attachments_valid = not attachment_error and all(
        attachment_form.is_valid() for attachment_form in attachment_forms
    )
    if request.method == 'POST' and agent_valid and attachments_valid:
        agent = form.save(commit=False)
        agent.updated_by_username = _username(request)
        agent.save()
        _save_attachment_forms(request, agent, attachment_forms)
        messages.success(request, 'Datos del agente actualizados.')
        return redirect('external_agents:agent_detail', pk=agent.pk)
    return render(request, 'external_agents/agent_form.html', {
        'form': form,
        'mode': 'edit',
        'agent': agent,
        'attachment_forms': attachment_forms,
        'empty_attachment_form': AttachmentForm(prefix='doc___index__'),
        'attachment_error': attachment_error,
        'attachment_types_available': (
            AttachmentForm().fields['document_type'].queryset.exists()
        ),
    })


@external_agent_access_required
def agent_detail(request, pk):
    agent = get_object_or_404(
        ExternalAgent.objects.select_related('personal_document_type'),
        pk=pk,
    )
    attachment_forms = _empty_attachment_forms()
    empty_attachment_form = AttachmentForm(prefix='doc___index__')
    return render(request, 'external_agents/agent_detail.html', {
        'agent': agent,
        'attachments': agent.attachments.select_related('document_type'),
        'attachment_forms': attachment_forms,
        'empty_attachment_form': empty_attachment_form,
        'attachment_types_available': (
            empty_attachment_form.fields['document_type'].queryset.exists()
        ),
    })


@external_agent_access_required
def attachment_upload(request, pk):
    agent = get_object_or_404(ExternalAgent, pk=pk)
    if request.method != 'POST':
        return redirect('external_agents:agent_detail', pk=pk)

    forms, attachment_error = _attachment_forms_from_request(request)
    if attachment_error:
        messages.error(request, attachment_error)
    elif not forms:
        messages.error(request, 'Selecciona al menos un tipo y un archivo.')
    elif not all(form.is_valid() for form in forms):
        for form in forms:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
    else:
        _save_attachment_forms(request, agent, forms)
    return redirect('external_agents:agent_detail', pk=pk)


@external_agent_access_required
def attachment_download(request, pk, attachment_pk):
    attachment = get_object_or_404(
        ExternalAgentAttachment,
        pk=attachment_pk,
        agent_id=pk,
    )
    try:
        file_handle = attachment.file.storage.open(attachment.file.name, 'rb')
    except Exception as exc:
        raise Http404('No se pudo recuperar el documento adjunto.') from exc
    filename = attachment.original_name or Path(attachment.file.name).name
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
        content_type=content_type,
    )


@external_agent_access_required
def attachment_preview(request, pk, attachment_pk):
    attachment = get_object_or_404(
        ExternalAgentAttachment,
        pk=attachment_pk,
        agent_id=pk,
    )
    try:
        file_handle = attachment.file.storage.open(attachment.file.name, 'rb')
    except Exception as exc:
        raise Http404('No se pudo recuperar el documento adjunto.') from exc
    filename = attachment.display_name
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    if content_type not in {
        'application/pdf',
        'image/jpeg',
        'image/png',
        'image/webp',
    }:
        raise Http404('Este tipo de archivo no tiene vista previa.')
    response = FileResponse(
        file_handle,
        as_attachment=False,
        filename=filename,
        content_type=content_type,
    )
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['Cache-Control'] = 'private, max-age=300'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@external_agent_access_required
def attachment_delete(request, pk, attachment_pk):
    attachment = get_object_or_404(
        ExternalAgentAttachment,
        pk=attachment_pk,
        agent_id=pk,
    )
    if request.method != 'POST':
        return redirect('external_agents:agent_detail', pk=pk)
    storage = attachment.file.storage
    stored_name = attachment.file.name
    attachment.delete()
    try:
        storage.delete(stored_name)
    except Exception:
        messages.warning(
            request,
            'El registro se eliminó, pero el archivo remoto requiere limpieza manual.',
        )
    else:
        messages.success(request, 'Documento adjunto eliminado.')
    return redirect('external_agents:agent_detail', pk=pk)


@external_agent_access_required
def configuration(request):
    return render(request, 'external_agents/configuration.html', {
        'personal_types': DocumentType.objects.filter(
            scope=DocumentType.Scope.PERSONAL,
        ).annotate(
            agent_count=Count('agents', distinct=True),
        ).order_by('sort_order', 'name', 'pk'),
        'attachment_types': DocumentType.objects.filter(
            scope=DocumentType.Scope.ATTACHMENT,
        ).annotate(
            attachment_count=Count('attachments', distinct=True),
        ).order_by('sort_order', 'name', 'pk'),
        'personal_form': DocumentTypeForm(),
        'attachment_form': DocumentTypeForm(),
    })


@external_agent_access_required
def document_type_create(request):
    if request.method != 'POST':
        return redirect('external_agents:configuration')
    scope = str(request.POST.get('scope') or '').strip()
    if scope not in DocumentType.Scope.values:
        messages.error(request, 'La categoría del tipo de documento no es válida.')
        return redirect('external_agents:configuration')

    form = DocumentTypeForm(request.POST)
    if form.is_valid():
        document_type = form.save(commit=False)
        document_type.scope = scope
        document_type.created_by_username = _username(request)
        document_type.save()
        messages.success(request, f'Tipo de documento “{document_type.name}” creado.')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect('external_agents:configuration')


@external_agent_access_required
def document_type_update(request, pk):
    document_type = get_object_or_404(DocumentType, pk=pk)
    if request.method != 'POST':
        return redirect('external_agents:configuration')
    form = DocumentTypeForm(request.POST, instance=document_type)
    if form.is_valid():
        form.save()
        messages.success(request, 'Tipo de documento actualizado.')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect('external_agents:configuration')


@external_agent_access_required
def document_type_toggle(request, pk):
    document_type = get_object_or_404(DocumentType, pk=pk)
    if request.method != 'POST':
        return redirect('external_agents:configuration')
    document_type.is_active = not document_type.is_active
    document_type.save(update_fields=['is_active', 'updated_at'])
    state = 'activado' if document_type.is_active else 'desactivado'
    messages.success(request, f'Tipo de documento {state}.')
    return redirect('external_agents:configuration')
