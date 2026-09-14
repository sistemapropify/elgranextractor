"""Read-only descriptions of control obligations; does not change SLA rules."""
from datetime import datetime, time, timedelta
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.core.paginator import Paginator
from django.utils import timezone
from .remarketing_engine import LIMA


def day_bounds(now):
    today = timezone.localtime(now, LIMA).date()
    start = datetime.combine(today, time.min, tzinfo=LIMA)
    return start, start + timedelta(days=1)


def entry_label(value, now):
    if not value:
        return 'Sin fecha de ingreso'
    day = timezone.localtime(value, LIMA).date()
    today = timezone.localtime(now, LIMA).date()
    relative = 'Hoy' if day == today else 'Ayer' if day == today-timedelta(days=1) else 'Ingreso'
    return f'{relative} · {day:%d/%m/%Y}'


def duration(delta):
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 1:
        return 'menos de 1 min'
    days, rest = divmod(minutes, 1440)
    hours, minutes = divmod(rest, 60)
    return f'{days} d {hours} h' if days else f'{hours} h {minutes} min' if hours else f'{minutes} min'


def describe(item, now, stale_before):
    fresh = bool(item.lead.quality == 'valid' and item.lead.observed_at and item.lead.observed_at >= stale_before)
    evidence = item.action.diagnosis.evidence if item.action.diagnosis_id else {}
    evidence = evidence if isinstance(evidence, dict) else {}
    reasons = {
        'first_response': 'No se ha registrado una primera respuesta humana al lead.',
        'reply': 'Hay un mensaje del cliente sin una respuesta humana posterior registrada.',
        'followup': 'Después del último contacto del asesor, corresponde retomar el seguimiento. No significa que el cliente esté esperando respuesta.',
        'assignment': 'Falta asignar un responsable para atender al lead.',
        'visit': 'Hay una intención o solicitud de visita pendiente de coordinar.',
        'commitment': 'Se registró un compromiso de próxima atención que sigue pendiente.',
        'postvisit': 'Falta registrar el resultado después de la visita.',
        'data': 'Es necesario verificar la información antes de evaluar la atención.',
    }
    item.source_fresh = fresh
    item.entry_group = entry_label(item.lead.entered_at, now)
    item.reason_text = reasons.get(item.kind, item.action.reason or item.action.title)
    if evidence.get('type') == 'crm_entry':
        item.reason_text = 'El lead ingresó al CRM, pero no hay una primera atención humana registrada. No se ha identificado un mensaje del cliente.'
    raw = evidence.get('message') or evidence.get('notes') or ''
    item.evidence_text = ' '.join(raw.split())[:240] if isinstance(raw, str) else ''
    item.evidence_label = 'Mensaje que originó el pendiente' if evidence.get('message') else 'Compromiso registrado'
    item.elapsed_text = f'Hace {duration(now-item.started_at)}' if item.started_at <= now else 'Inicio programado'
    due = item.action.due_at
    if not fresh:
        item.deadline_text, item.deadline_tone = 'Datos por verificar', 'unknown'
    elif not due:
        item.deadline_text, item.deadline_tone = 'Sin plazo registrado', 'unknown'
    elif due < now:
        item.deadline_text, item.deadline_tone = f'{duration(now-due)} de atraso', 'late'
    else:
        item.deadline_text, item.deadline_tone = f'Vence en {duration(due-now)}', 'scheduled'
    return item


def notice_description(notice, transport):
    channels = {'internal': 'Tablero', 'push': 'APK', 'email': 'Correo'}
    statuses = {'available': 'Disponible solo en el tablero', 'unroutable': 'Sin destinatario configurado',
                'pending': 'Pendiente de envío', 'accepted': 'Aceptado por el proveedor (no confirma lectura)',
                'uncertain': 'Envío sin confirmar', 'failed': 'Falló el envío', 'sending': 'Envío en proceso',
                'cancelled': 'Cancelado; no se enviará'}
    notice.channel_label = channels.get(notice.channel, notice.channel)
    notice.status_label = statuses.get(notice.status, notice.status)
    if notice.status == 'pending' and notice.channel in ('push', 'email') and not transport.get(notice.channel):
        notice.status_label = 'No se envía: canal deshabilitado'
    notice.level_label = {'agent': 'Asesor', 'supervisor': 'Supervisor', 'manager': 'Gerencia', 'data': 'Verificación', 'visit': 'Visita'}.get(notice.level, notice.level)
    return notice


def page_context(params, pending, now, stale_before):
    """Date filters refer ONLY to CRM entry. Pagination retains every filter."""
    fresh = Q(lead__quality='valid', lead__observed_at__gte=stale_before)
    start, end = day_bounds(now)
    period = params.get('entry', '')
    entry_filters = {'today': Q(lead__entered_at__gte=start, lead__entered_at__lt=end),
                     'yesterday': Q(lead__entered_at__gte=start-timedelta(days=1), lead__entered_at__lt=start),
                     'older': Q(lead__entered_at__lt=start-timedelta(days=1)),
                     'unknown': Q(lead__entered_at__isnull=True)}
    if period in entry_filters:
        pending = pending.filter(entry_filters[period])
    else:
        period = ''
    if params.get('overdue') == '1':
        pending = pending.filter(fresh, action__due_at__lt=now)
    if params.get('escalated') == '1':
        pending = pending.filter(fresh, manager_at__lte=now)
    order = params.get('order', 'recent')
    if order == 'priority':
        pending = pending.annotate(control_rank=Case(
            When(fresh & Q(manager_at__lte=now), then=Value(0)),
            When(fresh & Q(action__due_at__lt=now), then=Value(1)),
            When(fresh & Q(kind__in=['first_response', 'reply', 'visit']), then=Value(2)),
            default=Value(3), output_field=IntegerField(),
        )).order_by('control_rank', F('action__due_at').asc(nulls_last=True), '-pk')
    else:
        order = 'oldest' if order == 'oldest' else 'recent'
        entered = F('lead__entered_at').asc(nulls_last=True) if order == 'oldest' else F('lead__entered_at').desc(nulls_last=True)
        pending = pending.order_by(entered, '-lead__source_lead_id', 'started_at', 'pk')
    summary = pending.aggregate(
        actions=Count('pk'), leads=Count('lead_id', distinct=True),
        overdue=Count('pk', filter=fresh & Q(action__due_at__lt=now)),
        unverified=Count('pk', filter=~fresh),
        reply=Count('lead_id', distinct=True, filter=fresh & Q(kind__in=['first_response', 'reply'])),
        followup=Count('lead_id', distinct=True, filter=fresh & Q(kind='followup')),
    )
    query = params.copy()
    query.pop('page', None)
    return {'page': Paginator(pending, 50).get_page(params.get('page')), 'summary': summary,
            'entry_filter': period, 'order': order, 'page_query': query.urlencode(),
            'overdue_filter': params.get('overdue') == '1', 'escalated_filter': params.get('escalated') == '1'}
