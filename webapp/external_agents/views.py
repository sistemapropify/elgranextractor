import calendar
import mimetypes
import re
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import quote, urlencode

from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db import DatabaseError, connections, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
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
)

from .forms import AttachmentForm, DocumentTypeForm, ExternalAgentForm
from .models import (
    CommissionCollection,
    CommissionCollectionEntry,
    CommissionPayment,
    DocumentType,
    ExternalAgent,
    ExternalAgentAttachment,
    ServicePayment,
)


MAX_ATTACHMENTS_PER_SUBMISSION = 20
INITIAL_ATTACHMENT_ROWS = 6
PROPIFY_MEDIA_BASE_URL = 'https://propifymedia01.blob.core.windows.net/media'


def _propify_closings_from_database():
    """Lee en vivo los cierres activos desde la base dbpropify_be."""
    try:
        with connections['propifai'].cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    p.code,
                    p.title,
                    COALESCE(media.thumbnail, media.[file]) AS property_image,
                    c.deal_type,
                    c.status,
                    c.closing_date,
                    c.amount,
                    cu.code AS currency_code,
                    c.commission_pct,
                    c.commission_amount,
                    c.agents_amount,
                    c.brokers_amount,
                    c.propify_amount,
                    c.is_verified
                FROM closing c
                INNER JOIN property p ON p.id = c.property_id
                LEFT JOIN currency cu ON cu.id = c.currency_id
                OUTER APPLY (
                    SELECT TOP 1 pm.thumbnail, pm.[file]
                    FROM property_media pm
                    WHERE pm.property_id = p.id
                      AND pm.media_type = 'image'
                      AND (pm.thumbnail IS NOT NULL OR pm.[file] IS NOT NULL)
                    ORDER BY pm.[order], pm.id
                ) media
                WHERE c.status = %s
                ORDER BY c.closing_date DESC, c.id DESC
                """,
                ['active'],
            )
            columns = [
                'id',
                'property_code',
                'property_title',
                'property_image',
                'deal_type',
                'status',
                'closing_date',
                'amount',
                'currency_code',
                'commission_pct',
                'commission_amount',
                'agents_amount',
                'brokers_amount',
                'propify_amount',
                'is_verified',
            ]
            closings = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
            closing_ids = [item['id'] for item in closings]
            sides_by_closing = {closing_id: [] for closing_id in closing_ids}
            if closing_ids:
                placeholders = ', '.join(['%s'] * len(closing_ids))
                cursor.execute(
                    f"""
                    SELECT
                        s.closing_id,
                        s.role,
                        s.share_pct,
                        s.agent_pct,
                        s.side_amount,
                        s.agent_amount,
                        s.broker_pct,
                        s.broker_amount,
                        a.first_name,
                        a.last_name,
                        a.username,
                        b.first_name,
                        b.last_name,
                        b.username
                    FROM closing_side s
                    LEFT JOIN [user] a ON a.id = s.agent_id
                    LEFT JOIN [user] b ON b.id = s.broker_id
                    WHERE s.closing_id IN ({placeholders})
                    ORDER BY s.closing_id, s.id
                    """,
                    closing_ids,
                )
                for side_row in cursor.fetchall():
                    (
                        closing_id,
                        role,
                        share_pct,
                        agent_pct,
                        side_amount,
                        agent_amount,
                        broker_pct,
                        broker_amount,
                        agent_first_name,
                        agent_last_name,
                        agent_username,
                        broker_first_name,
                        broker_last_name,
                        broker_username,
                    ) = side_row
                    agent_name = (
                        f'{agent_first_name or ""} {agent_last_name or ""}'.strip()
                        or agent_username
                        or '—'
                    )
                    broker_name = (
                        f'{broker_first_name or ""} {broker_last_name or ""}'.strip()
                        or broker_username
                        or ''
                    )
                    sides_by_closing[closing_id].append({
                        'role': role,
                        'share_pct': share_pct,
                        'agent_pct': agent_pct,
                        'side_amount': side_amount,
                        'agent_amount': agent_amount,
                        'agent_name': agent_name,
                        'broker_pct': broker_pct,
                        'broker_amount': broker_amount,
                        'broker_name': broker_name,
                    })
            for item in closings:
                item['sides'] = sides_by_closing.get(item['id'], [])
        return closings, None
    except (KeyError, DatabaseError):
        return None, {
            'status': 503,
            'message': 'No se pudo consultar la base de datos de cierres de Propify.',
        }


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


def _closing_deal_type(item):
    raw_type = str(
        item.get('deal_type')
        or item.get('operation_type_name')
        or item.get('operation_type')
        or ''
    ).strip().lower()
    if 'alquiler' in raw_type or raw_type in {'rent', 'rental'}:
        return 'rent'
    return 'sale'


def _normalize_closing(item):
    item = item or {}
    property_value = item.get('property')
    if isinstance(property_value, dict):
        property_name = property_value.get('name') or property_value.get('title') or '—'
    else:
        property_name = (
            item.get('property_title')
            or item.get('property_name')
            or item.get('title')
            or item.get('address')
            or '—'
        )
    amount = _first_number(
        item.get('closing_amount_usd', item.get('amount', item.get('closing_amount'))),
        0,
    )
    commission_pct = _first_number(
        item.get('commission_pct', item.get('commission_final')),
        0,
    )
    commission_amount = _first_number(
        item.get('commission_amount', item.get('commission_total_amount')),
        amount * commission_pct / 100,
    )
    currency = item.get('currency')
    if isinstance(currency, dict):
        currency_code = str(currency.get('code') or '').strip().upper()
    else:
        currency_code = ''
    currency_code = (
        str(item.get('currency_code') or '').strip().upper()
        or currency_code
        or 'USD'
    )
    sides = item.get('sides') or item.get('agents_detail') or []
    if not isinstance(sides, list):
        sides = []
    if not sides and item.get('responsible_name'):
        fallback_agent_amount = _first_number(
            item.get('commission_agent_amount'),
            0,
        )
        fallback_agent_pct = (
            fallback_agent_amount / commission_amount * 100
            if commission_amount > 0
            else 0
        )
        sides = [{
            'role': 'listing',
            'role_display': 'Captación',
            'agent_name': item.get('responsible_name'),
            'share_pct': 100,
            'agent_pct': fallback_agent_pct,
            'side_amount': commission_amount,
            'agent_amount': fallback_agent_amount,
        }]
    agents = []
    brokers = []
    payables = []
    for side in sides:
        if not isinstance(side, dict):
            continue
        role = str(side.get('role') or '').lower()
        if (
            'capta' in role
            or 'vent' in role
            or role in {'listing', 'seller', 'vendedor'}
        ):
            side_label = 'Captación'
            beneficiary_type = CommissionPayment.BeneficiaryType.SELLER
        elif 'compra' in role or role in {'buyer', 'comprador'}:
            side_label = 'Comprador'
            beneficiary_type = CommissionPayment.BeneficiaryType.BUYER
        else:
            side_label = str(side.get('label') or side.get('role') or 'Agente')
            beneficiary_type = CommissionPayment.BeneficiaryType.OTHER

        side_amount = _first_number(
            side.get('side_amount'),
            commission_amount * _first_number(side.get('share_pct'), 0) / 100,
        )
        agent_pct = _first_number(side.get('agent_pct'), 0)
        agent_name = _agent_name(side)
        agent_amount = _first_number(
            side.get('agent_amount'),
            side_amount * agent_pct / 100,
        )
        agent = {
            'name': agent_name,
            'label': side_label,
            'type': beneficiary_type,
            'share_pct': _first_number(side.get('share_pct'), 0),
            'pct': agent_pct,
            'side_amount': side_amount,
            'amount': agent_amount,
        }
        agents.append(agent)
        if agent_amount > 0 and agent_name not in {'', '—'}:
            payables.append({
                **agent,
                'key': f'{beneficiary_type}:{agent_name}',
                'beneficiary_name': agent_name,
            })

        broker_name = str(
            side.get('broker_name')
            or _agent_name(side.get('broker'))
            or ''
        ).strip()
        broker_amount = _first_number(side.get('broker_amount'), 0)
        if broker_amount > 0 and broker_name not in {'', '—'}:
            broker = {
                'name': broker_name,
                'label': f'Broker · {side_label}',
                'type': CommissionPayment.BeneficiaryType.OTHER,
                'pct': _first_number(side.get('broker_pct'), 0),
                'amount': broker_amount,
                'key': f'otro:{broker_name}:{side_label}',
                'beneficiary_name': broker_name,
            }
            brokers.append(broker)
            payables.append(broker)

    agents_total = _first_number(
        item.get('agents_amount'),
        sum(agent['amount'] for agent in agents),
    )
    brokers_total = _first_number(
        item.get('brokers_amount'),
        sum(broker['amount'] for broker in brokers),
    )
    commission_propify = _first_number(
        item.get('propify_amount', item.get('commission_propify_amount')),
        max(commission_amount - agents_total - brokers_total, 0),
    )
    if commission_propify > 0:
        payables.append({
            'name': 'Propify',
            'label': 'Servicio Propify',
            'type': CommissionPayment.BeneficiaryType.PROPIFFY,
            'pct': (
                commission_propify / commission_amount * 100
                if commission_amount > 0
                else 0
            ),
            'amount': commission_propify,
            'key': 'propify:Propify',
            'beneficiary_name': 'Propify',
        })
    payable_order = {
        CommissionPayment.BeneficiaryType.PROPIFFY: 0,
        CommissionPayment.BeneficiaryType.SELLER: 1,
        CommissionPayment.BeneficiaryType.BUYER: 2,
        CommissionPayment.BeneficiaryType.OTHER: 3,
    }
    payables.sort(key=lambda payable: payable_order.get(payable['type'], 4))

    displayed_status = item.get('status') or item.get('closing_status') or ''
    if item.get('is_verified') is True:
        displayed_status = 'Verificado'
    elif item.get('is_verified') is False:
        displayed_status = 'Pendiente de verificar'
    closing_date = item.get('closing_date') or '—'
    parsed_closing_date = _parse_closing_date(closing_date)
    property_image = str(item.get('property_image') or '').strip()
    image_url = (
        f'{PROPIFY_MEDIA_BASE_URL}/{quote(property_image.replace(chr(92), "/").lstrip("/"), safe="/")}'
        if property_image
        else ''
    )
    return {
        'id': item.get('id') or item.get('pk') or '—',
        'code': (
            item.get('code')
            or item.get('operation_code')
            or item.get('property_code')
            or '—'
        ),
        'property': property_name,
        'image_url': image_url,
        'date': closing_date,
        'date_display': (
            parsed_closing_date.strftime('%d/%m/%Y')
            if parsed_closing_date
            else '—'
        ),
        'deal_type': _closing_deal_type(item),
        'amount': amount,
        'currency': currency_code,
        'commission_pct': commission_pct,
        'commission': commission_amount,
        'commission_propify': commission_propify,
        'agents_total': agents_total,
        'brokers_total': brokers_total,
        'collected': 0,
        'pending': commission_amount,
        'agents': agents,
        'brokers': brokers,
        'payables': payables,
        'status': displayed_status,
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
    """Sincroniza el cierre de Propify sin perder los abonos locales."""
    username = _username(request)
    for row in rows:
        key = _closing_key(row)
        if not key:
            continue
        amount = row.get('commission', 0)
        collection, created = CommissionCollection.objects.get_or_create(
            operation_code=key,
            defaults={
                'deal_type': row.get('deal_type') or 'sale',
                'property_name': row.get('property') or '',
                'amount_to_collect': amount,
                'amount_for_agents': row.get('agents_total', 0),
                'amount_for_brokers': row.get('brokers_total', 0),
                'amount_for_propify': row.get('commission_propify', 0),
                'currency_code': row.get('currency') or 'USD',
                'closing_date': _parse_closing_date(row.get('date')),
                'status': CommissionCollection.Status.PENDING,
                'created_by_username': username,
                'updated_by_username': username,
            },
        )
        if not created:
            collection.deal_type = row.get('deal_type') or collection.deal_type
            collection.property_name = row.get('property') or collection.property_name
            collection.amount_to_collect = amount
            collection.amount_for_agents = row.get('agents_total', 0)
            collection.amount_for_brokers = row.get('brokers_total', 0)
            collection.amount_for_propify = row.get('commission_propify', 0)
            collection.currency_code = row.get('currency') or collection.currency_code
            collection.closing_date = _parse_closing_date(row.get('date')) or collection.closing_date
            collection.updated_by_username = username
        _update_collection_status(collection)
        collection.save()
        row['collected'] = float(collection.collected_amount or 0)
        row['pending'] = max(
            float(collection.amount_to_collect or 0) - row['collected'],
            0,
        )
        row['collection_status'] = collection.get_status_display()


def _update_collection_status(collection):
    collected = collection.collected_amount or 0
    expected = collection.amount_to_collect or 0
    if collected <= 0:
        collection.status = CommissionCollection.Status.PENDING
    elif expected > 0 and collected >= expected:
        collection.status = CommissionCollection.Status.COLLECTED
    else:
        collection.status = CommissionCollection.Status.PARTIAL


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
    closings, error = _propify_closings_from_database()
    normalized_rows = [
        _normalize_closing(item)
        for item in (closings or [])
    ]
    _sync_commission_collections(normalized_rows, request)

    requested_deal = str(request.GET.get('tipo') or 'venta').strip().lower()
    deal_type = 'rent' if requested_deal in {'alquiler', 'alquileres', 'rent'} else 'sale'
    deal_slug = 'alquiler' if deal_type == 'rent' else 'venta'
    deal_label = 'Alquileres' if deal_type == 'rent' else 'Ventas'
    view_mode = str(request.GET.get('vista') or 'cierres').strip().lower()
    if view_mode not in {'cierres', 'cobros', 'pagos'}:
        view_mode = 'cierres'
    rows = [
        row for row in normalized_rows
        if row.get('deal_type') == deal_type
    ]
    deal_counts = {
        'sale': sum(row.get('deal_type') == 'sale' for row in normalized_rows),
        'rent': sum(row.get('deal_type') == 'rent' for row in normalized_rows),
    }
    active_codes = [
        row['code'] for row in rows
        if row.get('code') and row['code'] != '—'
    ]

    payments = list(
        CommissionPayment.objects
        .filter(
            operation_code__in=active_codes,
        )
        .exclude(status=CommissionPayment.Status.ANNULLED)
        .order_by('-payment_date', '-created_at', '-pk')
    )
    collection_entries = list(
        CommissionCollectionEntry.objects
        .filter(
            collection__deal_type=deal_type,
            collection__operation_code__in=active_codes,
        )
        .select_related('collection')
        .order_by('-collection_date', '-created_at', '-pk')[:30]
    )
    currency_summaries = []
    for currency in sorted({row.get('currency') or 'USD' for row in rows}):
        currency_rows = [
            row for row in rows
            if (row.get('currency') or 'USD') == currency
        ]
        currency_payments = [
            item for item in payments
            if (item.currency_code or 'USD') == currency
        ]
        commission = sum(float(row.get('commission') or 0) for row in currency_rows)
        collected = sum(float(row.get('collected') or 0) for row in currency_rows)
        agent_commission = sum(float(row.get('agents_total') or 0) for row in currency_rows)
        broker_commission = sum(float(row.get('brokers_total') or 0) for row in currency_rows)
        propify_commission = sum(
            float(row.get('commission_propify') or 0)
            for row in currency_rows
        )
        agents_paid = sum(
            float(item.amount or 0)
            for item in currency_payments
            if item.status == CommissionPayment.Status.PAID
            and item.beneficiary_type in {
                CommissionPayment.BeneficiaryType.SELLER,
                CommissionPayment.BeneficiaryType.BUYER,
            }
        )
        propify_paid = sum(
            float(item.amount or 0)
            for item in currency_payments
            if item.status == CommissionPayment.Status.PAID
            and item.beneficiary_type == CommissionPayment.BeneficiaryType.PROPIFFY
        )
        brokers_paid = sum(
            float(item.amount or 0)
            for item in currency_payments
            if item.status == CommissionPayment.Status.PAID
            and item.beneficiary_type == CommissionPayment.BeneficiaryType.OTHER
        )
        currency_summaries.append({
            'currency': currency,
            'count': len(currency_rows),
            'commission': commission,
            'collected': collected,
            'pending': max(commission - collected, 0),
            'agent_commission': agent_commission,
            'agents_paid': agents_paid,
            'agents_pending': max(agent_commission - agents_paid, 0),
            'broker_commission': broker_commission,
            'brokers_paid': brokers_paid,
            'brokers_pending': max(broker_commission - brokers_paid, 0),
            'propify_commission': propify_commission,
            'propify_paid': propify_paid,
            'propify_pending': max(propify_commission - propify_paid, 0),
        })

    summary = {
        'total': len(rows),
        'by_currency': currency_summaries,
        'deal_type': deal_type,
        'deal_slug': deal_slug,
        'deal_label': deal_label,
    }
    closing_data = [
        {
            'code': row['code'],
            'property': row['property'],
            'currency': row['currency'],
            'commission': row['commission'],
            'pending': row['pending'],
            'payables': row['payables'],
        }
        for row in rows
        if row['code'] != '—'
    ]
    return render(request, 'external_agents/cierres.html', {
        'rows': rows,
        'summary': summary,
        'error': error,
        'deal_type': deal_type,
        'deal_slug': deal_slug,
        'deal_label': deal_label,
        'deal_counts': deal_counts,
        'view_mode': view_mode,
        'closing_data': closing_data,
        'payments': payments[:30],
        'collection_entries': collection_entries,
        'beneficiary_types': CommissionPayment.BeneficiaryType.choices,
        'payment_statuses': CommissionPayment.Status.choices,
    })


def _parse_date_input(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _redirect_cierres(deal_type=None, view_mode=None):
    params = {}
    if deal_type in {'sale', 'rent'}:
        params['tipo'] = 'alquiler' if deal_type == 'rent' else 'venta'
    if view_mode in {'cierres', 'cobros', 'pagos'}:
        params['vista'] = view_mode
    url = reverse('external_agents:cierres')
    return redirect(f'{url}?{urlencode(params)}' if params else url)


@never_cache
@external_agent_access_required
def collection_add(request):
    if request.method != 'POST':
        return _redirect_cierres()
    deal_type = str(request.POST.get('deal_type') or '').strip()
    operation_code = str(request.POST.get('operation_code') or '').strip()
    amount = _first_number(request.POST.get('amount'))
    if not operation_code or amount <= 0:
        messages.error(request, 'Selecciona un cierre y un monto válido.')
        return _redirect_cierres(deal_type, 'cobros')
    with transaction.atomic():
        try:
            collection = (
                CommissionCollection.objects
                .select_for_update()
                .get(operation_code=operation_code)
            )
        except CommissionCollection.DoesNotExist:
            messages.error(request, 'El cierre seleccionado ya no está disponible.')
            return _redirect_cierres(deal_type, 'cobros')
        remaining = max(
            float(collection.amount_to_collect or 0)
            - float(collection.collected_amount or 0),
            0,
        )
        if remaining <= 0:
            messages.error(request, 'Este cierre ya no tiene saldo pendiente de cobro.')
            return _redirect_cierres(collection.deal_type, 'cobros')
        if amount - remaining > 0.005:
            messages.error(
                request,
                f'El abono supera el saldo pendiente de '
                f'{collection.currency_code} {remaining:,.2f}.',
            )
            return _redirect_cierres(collection.deal_type, 'cobros')
        CommissionCollectionEntry.objects.create(
            collection=collection,
            amount=amount,
            collection_date=(
                _parse_date_input(request.POST.get('collection_date'))
                or timezone.localdate()
            ),
            payment_method=str(request.POST.get('payment_method') or '').strip(),
            account=str(request.POST.get('account') or '').strip(),
            voucher=str(request.POST.get('voucher') or '').strip(),
            notes=str(request.POST.get('notes') or '').strip(),
            registered_by_username=_username(request),
        )
        collection.collected_amount = (
            _first_number(collection.collected_amount) + amount
        )
        collection.updated_by_username = _username(request)
        _update_collection_status(collection)
        collection.save(update_fields=[
            'collected_amount',
            'status',
            'updated_by_username',
            'updated_at',
        ])
    messages.success(request, 'Abono registrado en el historial del cierre.')
    return _redirect_cierres(collection.deal_type, 'cobros')


@never_cache
@external_agent_access_required
def payment_add(request):
    if request.method != 'POST':
        return _redirect_cierres()
    deal_type = str(request.POST.get('deal_type') or '').strip()
    operation_code = str(request.POST.get('operation_code') or '').strip()
    beneficiary_type = str(request.POST.get('beneficiary_type') or '').strip()
    beneficiary_name = str(request.POST.get('beneficiary_name') or '').strip()
    beneficiary_choice = str(request.POST.get('beneficiary_choice') or '').strip()
    if beneficiary_choice and (not beneficiary_type or not beneficiary_name):
        choice_type, _, choice_name = beneficiary_choice.partition(':')
        beneficiary_type = beneficiary_type or choice_type
        beneficiary_name = beneficiary_name or choice_name.split(':', 1)[0]
    amount = _first_number(request.POST.get('amount'))
    valid_types = {value for value, _ in CommissionPayment.BeneficiaryType.choices}
    valid_statuses = {value for value, _ in CommissionPayment.Status.choices}
    status = str(
        request.POST.get('status') or CommissionPayment.Status.PAID
    ).strip()
    if (
        not operation_code
        or beneficiary_type not in valid_types
        or status not in valid_statuses
        or amount <= 0
    ):
        messages.error(request, 'Revisa los datos del pago antes de guardarlo.')
        return _redirect_cierres(deal_type, 'pagos')
    try:
        collection = CommissionCollection.objects.get(operation_code=operation_code)
    except CommissionCollection.DoesNotExist:
        messages.error(request, 'El cierre seleccionado ya no está disponible.')
        return _redirect_cierres(deal_type, 'pagos')
    payment_date = (
        _parse_date_input(request.POST.get('payment_date'))
        or timezone.localdate()
    )
    payment = CommissionPayment(
        operation_code=operation_code,
        property_name=collection.property_name,
        beneficiary_type=beneficiary_type,
        beneficiary_name=beneficiary_name,
        amount=amount,
        currency_code=(
            str(request.POST.get('currency_code') or '').strip().upper()
            or collection.currency_code
            or 'USD'
        ),
        due_date=None,
        payment_date=payment_date,
        status=status,
        payment_method=str(request.POST.get('payment_method') or '').strip(),
        account=str(request.POST.get('account') or '').strip(),
        voucher=str(request.POST.get('voucher') or '').strip(),
        approved_by=str(request.POST.get('approved_by') or '').strip(),
        notes=str(request.POST.get('notes') or '').strip(),
        created_by_username=_username(request),
        updated_by_username=_username(request),
    )
    payment.save()
    messages.success(request, 'Pago registrado correctamente.')
    return _redirect_cierres(collection.deal_type, 'pagos')


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_service_due_date(value, recurrence):
    months = {
        ServicePayment.Recurrence.MONTHLY: 1,
        ServicePayment.Recurrence.BIMONTHLY: 2,
        ServicePayment.Recurrence.QUARTERLY: 3,
        ServicePayment.Recurrence.ANNUAL: 12,
    }.get(recurrence)
    return _add_months(value, months) if months else None


@never_cache
@external_agent_access_required
def service_payments(request):
    query = str(request.GET.get('q') or '').strip()
    status_filter = str(request.GET.get('estado') or 'pendientes').strip()
    category_filter = str(request.GET.get('categoria') or '').strip()
    payments = ServicePayment.objects.all()
    if query:
        payments = payments.filter(
            Q(concept__icontains=query)
            | Q(provider__icontains=query)
            | Q(reference__icontains=query)
            | Q(notes__icontains=query)
        )
    if category_filter in ServicePayment.Category.values:
        payments = payments.filter(category=category_filter)
    today = timezone.localdate()
    if status_filter == 'pagados':
        payments = payments.filter(status=ServicePayment.Status.PAID)
    elif status_filter == 'vencidos':
        payments = payments.filter(
            status=ServicePayment.Status.PENDING,
            due_date__lt=today,
        )
    elif status_filter == 'todos':
        pass
    else:
        payments = payments.filter(status=ServicePayment.Status.PENDING)

    rows = []
    for payment in payments:
        if payment.status == ServicePayment.Status.PAID:
            display_status = 'Pagado'
            status_class = 'green'
        elif payment.due_date < today:
            display_status = 'Vencido'
            status_class = 'red'
        elif payment.due_date == today:
            display_status = 'Vence hoy'
            status_class = 'amber'
        else:
            display_status = 'Pendiente'
            status_class = 'amber'
        alarm_date = payment.due_date - timedelta(
            days=payment.reminder_days_before
        )
        rows.append({
            'payment': payment,
            'display_status': display_status,
            'status_class': status_class,
            'alarm_date': alarm_date,
            'alarm_active': (
                payment.status == ServicePayment.Status.PENDING
                and alarm_date <= today
            ),
        })

    pending = ServicePayment.objects.filter(status=ServicePayment.Status.PENDING)
    summary = {
        'pending': pending.count(),
        'due_today': pending.filter(due_date=today).count(),
        'overdue': pending.filter(due_date__lt=today).count(),
        'paid_month': ServicePayment.objects.filter(
            status=ServicePayment.Status.PAID,
            payment_date__year=today.year,
            payment_date__month=today.month,
        ).count(),
    }
    return render(request, 'external_agents/pagos_servicios.html', {
        'rows': rows,
        'summary': summary,
        'query': query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'categories': ServicePayment.Category.choices,
    })


@never_cache
@external_agent_access_required
def service_payment_add(request):
    if request.method != 'POST':
        return redirect('external_agents:service_payments')
    valid_categories = set(ServicePayment.Category.values)
    valid_recurrences = set(ServicePayment.Recurrence.values)
    concept = str(request.POST.get('concept') or '').strip()
    category = str(request.POST.get('category') or '').strip()
    recurrence = str(request.POST.get('recurrence') or '').strip()
    due_date = _parse_date_input(request.POST.get('due_date'))
    if (
        not concept
        or category not in valid_categories
        or recurrence not in valid_recurrences
        or due_date is None
    ):
        messages.error(request, 'Completa el concepto, categoría, periodicidad y vencimiento.')
        return redirect('external_agents:service_payments')
    ServicePayment.objects.create(
        concept=concept,
        provider=str(request.POST.get('provider') or '').strip(),
        reference=str(request.POST.get('reference') or '').strip(),
        category=category,
        recurrence=recurrence,
        currency_code=(
            str(request.POST.get('currency_code') or '').strip().upper()
            or 'PEN'
        ),
        estimated_amount=_first_number(request.POST.get('estimated_amount')),
        due_date=due_date,
        reminder_days_before=max(
            int(_first_number(request.POST.get('reminder_days_before'), 3)),
            0,
        ),
        notes=str(request.POST.get('notes') or '').strip(),
        created_by_username=_username(request),
        updated_by_username=_username(request),
    )
    messages.success(request, 'Pago programado correctamente.')
    return redirect('external_agents:service_payments')


@never_cache
@external_agent_access_required
def service_payment_pay(request, pk):
    payment = get_object_or_404(ServicePayment, pk=pk)
    if request.method != 'POST':
        return redirect('external_agents:service_payments')
    payment.paid_amount = (
        _first_number(request.POST.get('paid_amount'))
        or _first_number(payment.estimated_amount)
    )
    payment.payment_date = (
        _parse_date_input(request.POST.get('payment_date'))
        or timezone.localdate()
    )
    payment.status = ServicePayment.Status.PAID
    payment.payment_method = str(request.POST.get('payment_method') or '').strip()
    payment.account = str(request.POST.get('account') or '').strip()
    payment.voucher = str(request.POST.get('voucher') or '').strip()
    payment.notes = str(request.POST.get('notes') or payment.notes).strip()
    payment.updated_by_username = _username(request)
    payment.save()
    next_due_date = _next_service_due_date(payment.due_date, payment.recurrence)
    if next_due_date:
        ServicePayment.objects.create(
            concept=payment.concept,
            provider=payment.provider,
            reference=payment.reference,
            category=payment.category,
            recurrence=payment.recurrence,
            currency_code=payment.currency_code,
            estimated_amount=payment.estimated_amount,
            due_date=next_due_date,
            reminder_days_before=payment.reminder_days_before,
            created_by_username=_username(request),
            updated_by_username=_username(request),
        )
    messages.success(request, 'Pago registrado. Estado actualizado a Pagado.')
    return redirect('external_agents:service_payments')


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
    if status == 'inactivos':
        agents = agents.filter(is_active=False)
    elif status != 'todos':
        agents = agents.filter(is_active=True)
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


@never_cache
@external_agent_access_required
def agent_toggle_active(request, pk):
    agent = get_object_or_404(ExternalAgent, pk=pk)
    if request.method == 'POST':
        agent.is_active = not agent.is_active
        agent.updated_by_username = _username(request)
        agent.save(update_fields=['is_active', 'updated_by_username', 'updated_at'])
        state = 'reactivado' if agent.is_active else 'desactivado'
        messages.success(
            request,
            f'Agente {state}. '
            + (
                'Vuelve a aparecer en el directorio.'
                if agent.is_active
                else 'Se ocultó del directorio, pero se conservaron sus datos y documentos.'
            ),
        )
    return redirect('external_agents:agent_detail', pk=pk)


@never_cache
@external_agent_access_required
def agent_delete(request, pk):
    agent = get_object_or_404(ExternalAgent, pk=pk)
    if request.method == 'POST':
        display_name = agent.display_name
        attachments = list(agent.attachments.all())
        with transaction.atomic():
            for attachment in attachments:
                try:
                    attachment.file.delete(save=False)
                except Exception:
                    # La ficha se elimina aunque Azure no pueda borrar un archivo.
                    pass
            agent.delete()
        messages.success(
            request,
            f'Registro de {display_name} eliminado definitivamente.',
        )
    return redirect('external_agents:dashboard')


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
