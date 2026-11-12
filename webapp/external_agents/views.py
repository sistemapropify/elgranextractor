import mimetypes
import re
from datetime import date
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

import requests
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin

from prospects.propify_auth import (
    WEB_REFRESH_SESSION_KEY,
    WEB_PROFILE_SESSION_KEY,
    WEB_TOKEN_SESSION_KEY,
    PropifyAuthError,
    authenticate_propify_credentials,
    clear_web_propify_session,
    get_web_propify_principal,
    refresh_propify_session,
)

from .forms import AttachmentForm, DocumentTypeForm, ExternalAgentForm
from .models import (
    CommissionCollection,
    DocumentType,
    ExternalAgent,
    ExternalAgentAttachment,
)


MAX_ATTACHMENTS_PER_SUBMISSION = 20
INITIAL_ATTACHMENT_ROWS = 6


def _closings_fallback_urls():
    urls = [
        getattr(settings, 'PROPIFY_CLOSINGS_URL', ''),
        getattr(settings, 'PROPIFY_MY_CLOSINGS_URL', ''),
    ]
    return [url for url in urls if url]


def _propify_closings(token):
    """Pide la lista de cierres a Propify y la normaliza a una lista plana."""
    ultimo_error = 'No se pudo conectar con Propify para cargar los cierres.'
    for url in _closings_fallback_urls():
        try:
            response = requests.get(
                url,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Accept': 'application/json',
                },
                timeout=15,
            )
        except requests.RequestException:
            ultimo_error = 'Propify no respondió al cargar los cierres.'
            continue
        if response.status_code in (401, 403):
            try:
                detail = response.json().get('detail')
            except ValueError:
                detail = None
            message = str(detail or 'Propify rechazó el acceso a los cierres.')
            return None, {
                'status': response.status_code,
                'message': message,
            }
        if response.status_code == 404:
            ultimo_error = 'Propify no expone el listado de cierres para este usuario.'
            continue
        if response.status_code != 200:
            ultimo_error = f'Propify devolvió el estado {response.status_code}.'
            continue
        try:
            payload = response.json()
        except ValueError:
            ultimo_error = 'Propify devolvió una respuesta inválida.'
            continue
        if isinstance(payload, list):
            return payload, None
        if isinstance(payload, dict):
            for key in ('results', 'data', 'closings'):
                if isinstance(payload.get(key), list):
                    return payload[key], None
        ultimo_error = 'Propify devolvió un listado de cierres con un formato desconocido.'
    return None, {'status': 502, 'message': ultimo_error}


def _first_number(value, default=0):
    try:
        if value in (None, ''):
            return default
        number = float(value)
        return number if number == number else default
    except (TypeError, ValueError):
        return default


def _agent_name(side):
    if not isinstance(side, dict):
        return '—'
    if side.get('agent_name'):
        return str(side['agent_name'])
    agent = side.get('agent')
    if isinstance(agent, dict):
        return str(agent.get('name') or agent.get('full_name') or '—')
    return str(side.get('name') or '—')


def _normalize_closing(item):
    item = item or {}
    property_value = item.get('property')
    if isinstance(property_value, dict):
        property_name = property_value.get('name') or property_value.get('title') or '—'
    else:
        property_name = (
            item.get('property_name')
            or item.get('property_title')
            or item.get('address')
            or '—'
        )
    amount = _first_number(
        item.get('closing_amount_usd', item.get('amount', item.get('closing_amount'))),
        0,
    )
    commission_amount = _first_number(
        item.get('commission_amount'),
        amount * _first_number(item.get('commission_pct', 0)) / 100,
    )
    payments = item.get('payments') or item.get('deposits') or []
    if isinstance(payments, list):
        collected = sum(
            _first_number(
                payment.get('amount') if isinstance(payment, dict) else payment,
                0,
            )
            for payment in payments
        )
    else:
        collected = _first_number(
            item.get('collected_amount', item.get('paid_amount')),
            0,
        )
    commission_propify = _first_number(
        item.get('commission_propify_amount'),
        amount * _first_number(item.get('commission_pf', 0)) / 100,
    )
    sides = item.get('sides') or item.get('agents_detail') or []
    if not isinstance(sides, list):
        sides = []
    agents = []
    for side in sides:
        if not isinstance(side, dict):
            continue
        role = str(side.get('role') or '').lower()
        if 'compra' in role or role in {'buyer', 'comprador'}:
            label = 'Comprador'
        elif 'vent' in role or role in {'seller', 'vendedor', 'propietario'}:
            label = 'Vendedor'
        else:
            label = str(side.get('label') or side.get('role') or 'Agente')
        pct = _first_number(side.get('agent_pct', side.get('share_pct')), 0)
        agents.append({
            'name': _agent_name(side),
            'label': label,
            'pct': pct,
            'amount': amount * pct / 100,
        })
    pending = max(commission_amount - collected, 0)
    return {
        'id': item.get('id') or item.get('pk') or '—',
        'code': item.get('code') or item.get('operation_code') or '—',
        'property': property_name,
        'date': item.get('closing_date') or '—',
        'amount': amount,
        'commission': commission_amount,
        'commission_propify': commission_propify,
        'collected': collected,
        'pending': pending,
        'agents': agents,
        'status': item.get('status') or item.get('closing_status') or '',
    }


def _closing_key(row):
    code = str(row.get('code') or '').strip()
    if code and code != '—':
        return code
    identifier = str(row.get('id') or '').strip()
    return f'CL-{identifier}' if identifier else ''


def _parse_closing_date(value):
    if not value or value == '—':
        return None
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        year, month, day = [int(part) for part in text.split('-')[:3]]
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _sync_commission_collections(rows, request):
    """Crea o actualiza el cobro local para cada cierre detectado."""
    username = _username(request)
    for row in rows:
        key = _closing_key(row)
        if not key:
            continue
        collected = row.get('collected', 0)
        amount = row.get('commission', 0)
        if collected <= 0:
            status = CommissionCollection.Status.PENDING
        elif collected >= amount > 0:
            status = CommissionCollection.Status.COLLECTED
        else:
            status = CommissionCollection.Status.PARTIAL
        collection, created = CommissionCollection.objects.get_or_create(
            operation_code=key,
            defaults={
                'property_name': row.get('property') or '',
                'amount_to_collect': amount,
                'collected_amount': collected,
                'closing_date': _parse_closing_date(row.get('date')),
                'status': status,
                'created_by_username': username,
                'updated_by_username': username,
            },
        )
        if not created:
            collection.property_name = row.get('property') or collection.property_name
            collection.amount_to_collect = amount
            collection.collected_amount = collected
            collection.closing_date = _parse_closing_date(row.get('date')) or collection.closing_date
            collection.status = status
            collection.updated_by_username = username
            collection.save(update_fields=[
                'property_name',
                'amount_to_collect',
                'collected_amount',
                'closing_date',
                'status',
                'updated_by_username',
                'updated_at',
            ])


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
                refresh_token = str(_.get('refresh') or '').strip()
                if refresh_token:
                    request.session[WEB_REFRESH_SESSION_KEY] = refresh_token
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


@never_cache
@external_agent_access_required
def cierres(request):
    token = str(request.session.get(WEB_TOKEN_SESSION_KEY, '')).strip()
    closings, error = _propify_closings(token)
    if error and error.get('status') in (401, 403):
        refresh_token = str(request.session.get(WEB_REFRESH_SESSION_KEY, '')).strip()
        if refresh_token:
            try:
                refreshed = refresh_propify_session(refresh_token)
            except PropifyAuthError:
                clear_web_propify_session(request)
                query = urlencode({'next': request.get_full_path()})
                return redirect(f'/agentes-externos/login/?{query}')
            request.session[WEB_TOKEN_SESSION_KEY] = refreshed['access']
            if refreshed.get('refresh'):
                request.session[WEB_REFRESH_SESSION_KEY] = refreshed['refresh']
            closings, error = _propify_closings(refreshed['access'])
        else:
            clear_web_propify_session(request)
            query = urlencode({'next': request.get_full_path()})
            return redirect(f'/agentes-externos/login/?{query}')
    rows = [_normalize_closing(item) for item in (closings or [])]
    _sync_commission_collections(rows, request)

    summary = {
        'total': len(rows),
        'commission': sum(row['commission'] for row in rows),
        'collected': sum(row['collected'] for row in rows),
        'pending': sum(row['pending'] for row in rows),
        'payable_agents': sum(
            agent['amount']
            for row in rows
            for agent in row['agents']
        ),
    }
    return render(request, 'external_agents/cierres.html', {
        'rows': rows,
        'summary': summary,
        'error': error,
    })


@never_cache
@external_agent_access_required
def dashboard(request):
    query = str(request.GET.get('q') or '').strip()
    status = str(request.GET.get('estado') or '').strip()
    document_type = str(request.GET.get('tipo_documento') or '').strip()
    level = str(request.GET.get('nivel') or '').strip()
    view_mode = (
        'table'
        if request.GET.get('vista') in {'matriz', 'table'}
        else 'cards'
    )
    agents = (
        ExternalAgent.objects
        .annotate(attachment_count=Count('attachments'))
        .prefetch_related('attachments__document_type')
    )

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
    view_query = request.GET.copy()
    view_query.pop('page', None)
    view_query.pop('vista', None)
    return render(request, 'external_agents/dashboard.html', {
        'page': page,
        'agents': page.object_list,
        'query': query,
        'status_filter': status,
        'document_type_filter': document_type,
        'level_filter': level,
        'view_mode': view_mode,
        'view_query': view_query.urlencode(),
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


@never_cache
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


@never_cache
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


@never_cache
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


@xframe_options_sameorigin
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
    response['X-Frame-Options'] = 'SAMEORIGIN'
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
