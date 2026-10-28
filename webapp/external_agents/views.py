import mimetypes
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
    agents = ExternalAgent.objects.annotate(attachment_count=Count('attachments'))

    if query:
        agents = agents.filter(
            Q(first_name__icontains=query)
            | Q(paternal_last_name__icontains=query)
            | Q(maternal_last_name__icontains=query)
            | Q(document_number__icontains=query)
            | Q(email__icontains=query)
            | Q(mobile__icontains=query)
        )
    if status == 'activos':
        agents = agents.filter(is_active=True)
    elif status == 'inactivos':
        agents = agents.filter(is_active=False)
    if document_type.isdigit():
        agents = agents.filter(personal_document_type_id=int(document_type))

    total_agents = ExternalAgent.objects.count()
    active_agents = ExternalAgent.objects.filter(is_active=True).count()
    with_attachments = ExternalAgent.objects.filter(attachments__isnull=False).distinct().count()
    without_attachments = ExternalAgent.objects.filter(
        attachments__isnull=True,
    ).count()

    paginator = Paginator(
        agents.select_related('personal_document_type').order_by(
            'paternal_last_name',
            'maternal_last_name',
            'first_name',
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
    form = ExternalAgentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        agent = form.save(commit=False)
        agent.created_by_username = _username(request)
        agent.updated_by_username = agent.created_by_username
        agent.save()
        messages.success(request, 'Agente externo registrado correctamente.')
        return redirect('external_agents:agent_detail', pk=agent.pk)
    return render(request, 'external_agents/agent_form.html', {
        'form': form,
        'mode': 'create',
        'agent': None,
    })


@external_agent_access_required
def agent_edit(request, pk):
    agent = get_object_or_404(ExternalAgent, pk=pk)
    form = ExternalAgentForm(request.POST or None, instance=agent)
    if request.method == 'POST' and form.is_valid():
        agent = form.save(commit=False)
        agent.updated_by_username = _username(request)
        agent.save()
        messages.success(request, 'Datos del agente actualizados.')
        return redirect('external_agents:agent_detail', pk=agent.pk)
    return render(request, 'external_agents/agent_form.html', {
        'form': form,
        'mode': 'edit',
        'agent': agent,
    })


@external_agent_access_required
def agent_detail(request, pk):
    agent = get_object_or_404(
        ExternalAgent.objects.select_related('personal_document_type'),
        pk=pk,
    )
    attachment_form = AttachmentForm()
    return render(request, 'external_agents/agent_detail.html', {
        'agent': agent,
        'attachments': agent.attachments.select_related('document_type'),
        'attachment_form': attachment_form,
        'attachment_types_available': (
            attachment_form.fields['document_type'].queryset.exists()
        ),
    })


@external_agent_access_required
def attachment_upload(request, pk):
    agent = get_object_or_404(ExternalAgent, pk=pk)
    if request.method != 'POST':
        return redirect('external_agents:agent_detail', pk=pk)

    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.agent = agent
        attachment.original_name = getattr(form, 'original_name', '')
        attachment.uploaded_by_username = _username(request)
        attachment.save()
        messages.success(request, 'Documento adjunto guardado.')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
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
