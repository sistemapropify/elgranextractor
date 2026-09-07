"""Persistent follow-up scheduling. Never invokes an LLM or sends from a web request."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .conversation_analysis import normalize_text
from .models import RemarketingCampaign, RemarketingDelivery, RemarketingEnrollment, RemarketingRuntime
from .remarketing_forms import render_message

LIMA = ZoneInfo('America/Lima')
RESERVED = ['sending', 'accepted', 'sent', 'delivered', 'uncertain']
CONFIRMED = ['sent', 'delivered']
POLICY_FIELDS = ['allowed_statuses', 'allowed_channels', 'agent_ids', 'contact_sender', 'daily_limit', 'hourly_limit', 'contact_limit', 'min_gap_minutes', 'window_margin_minutes', 'start_hour', 'end_hour', 'weekdays']


def as_time(value):
    result = parse_datetime(value) if isinstance(value, str) else value
    if not isinstance(result, datetime) or timezone.is_naive(result):
        raise ValueError('Fecha ausente o sin zona horaria.')
    return result


def timeline(snapshot):
    raw = snapshot.get('messages', [])
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError('Historial inválido.')
    items = []
    for item in raw:
        if not isinstance(item, dict) or item.get('sender') not in ('lead', 'agent', 'bot'):
            raise ValueError('Emisor no verificable.')
        items.append({**item, 'timestamp': as_time(item.get('timestamp')), 'text': str(item.get('text') or item.get('content') or '')})
    return sorted(items, key=lambda item: item['timestamp'])


def policy_for(campaign):
    return {name: getattr(campaign, name) for name in POLICY_FIELDS}


def eligibility(policy, snapshot, now):
    """Select the original contact once. Sending again never resets the anchor."""
    if snapshot.get('closed') or snapshot.get('contact_allowed') is False or snapshot.get('visit_intent') or snapshot.get('visit_scheduled'):
        return None, 'Contacto cerrado o excluido.'
    for key, field in [('status_name', 'allowed_statuses'), ('channel_name', 'allowed_channels')]:
        if normalize_text(snapshot.get(key)) not in {normalize_text(v) for v in policy[field]}:
            return None, 'Estado o canal fuera de las condiciones.'
    if policy['agent_ids'] and snapshot.get('agent_id') not in policy['agent_ids']:
        return None, 'Agente fuera de las condiciones.'
    if not snapshot.get('contact_key'):
        return None, 'Falta identidad del contacto.'
    messages = timeline(snapshot)
    if any(m['timestamp'] > now for m in messages):
        return None, 'Historial contiene fechas futuras.'
    inbound = next((m for m in messages if m['sender'] == 'lead'), None)
    if inbound is None:
        return None, 'Sin mensaje entrante verificable.'
    if any(re.search(r'\b(no (?:me )?interesa|no me escribas|no me contacten|numero equivocado|stop)\b', normalize_text(m['text'])) for m in messages if m['sender'] == 'lead'):
        return None, 'El cliente indicó rechazo o no contacto.'
    first_outbound = next((m for m in messages if m['timestamp'] >= inbound['timestamp'] and m['sender'] != 'lead'), None)
    if first_outbound and any(m['sender'] == 'lead' and m['timestamp'] >= first_outbound['timestamp'] for m in messages):
        return None, 'Ya existe conversación bidireccional.'
    contact = next((m for m in messages if m['timestamp'] >= inbound['timestamp'] and (m['sender'] == 'agent' or (policy['contact_sender'] == 'any' and m['sender'] == 'bot'))), None)
    if contact is None:
        return None, 'Sin primer contacto válido.'
    if any(m['sender'] == 'lead' and m['timestamp'] >= contact['timestamp'] for m in messages):
        return None, 'El cliente ya respondió.'
    last_inbound = max(m['timestamp'] for m in messages if m['sender'] == 'lead')
    expiry = last_inbound + timedelta(hours=24) - timedelta(minutes=policy['window_margin_minutes'])
    if now >= expiry:
        return None, 'Ventana de 24 horas agotada.'
    return {'anchor': contact['timestamp'], 'inbound': last_inbound, 'expiry': expiry}, ''


def enroll(campaign, snapshot, now=None):
    now = now or timezone.now()
    if campaign.status != 'active':
        return None, 'Campaña no activa.'
    policy = policy_for(campaign)
    revision = campaign.revision
    info, reason = eligibility(policy, snapshot, now)
    if not info:
        return None, reason
    # Global across campaigns and duplicated CRM lead records for this contact.
    episode = hashlib.sha256(f"{snapshot['contact_key']}:{info['anchor'].isoformat()}".encode()).hexdigest()
    context = {name: snapshot.get(name, '') for name in ('nombre', 'propiedad', 'agente')}
    steps = [(step, render_message(step.body, context)) for step in campaign.steps.all()]
    if not steps:
        return None, 'Campaña sin pasos.'
    RemarketingRuntime.objects.get_or_create(pk=1)
    with transaction.atomic():
        RemarketingRuntime.objects.select_for_update().get(pk=1)
        campaign = RemarketingCampaign.objects.select_for_update().get(pk=campaign.pk)
        if campaign.status != 'active' or campaign.revision != revision or policy_for(campaign) != policy:
            return None, 'La campaña cambió; se reevaluará.'
        existing = RemarketingEnrollment.objects.filter(episode_key=episode).first()
        if existing:
            return existing, 'Episodio ya registrado.'
        if RemarketingEnrollment.objects.filter(contact_key=snapshot['contact_key'], status='active').exists():
            return None, 'El contacto ya participa en otra secuencia.'
        enrollment = RemarketingEnrollment.objects.create(campaign=campaign, revision=campaign.revision, source_lead_id=snapshot['lead_id'], contact_key=snapshot['contact_key'], episode_key=episode, anchor_at=info['anchor'], last_inbound_at=info['inbound'], policy=policy, context={**context, 'agent_id': snapshot.get('agent_id')})
        for position, (step, body) in enumerate(steps, 1):
            due = info['anchor'] + timedelta(minutes=step.delay_minutes)
            expired = due >= info['expiry']
            RemarketingDelivery.objects.create(enrollment=enrollment, position=position, title=step.title, body=body, due_at=due, idempotency_key=uuid.uuid4(), status='skipped' if expired else 'pending', reason='Paso fuera de la ventana de 24 horas.' if expired else '')
        return enrollment, ''


def stop(enrollment, reason, response_at=None):
    enrollment.status = 'responded' if response_at else 'stopped'
    enrollment.stop_reason = reason
    enrollment.response_at = response_at
    enrollment.save(update_fields=['status', 'stop_reason', 'response_at'])
    enrollment.deliveries.filter(status='pending').update(status='cancelled', reason=reason)


def reconcile(enrollment, snapshot, now):
    messages = timeline(snapshot)
    response = next((m for m in messages if m['sender'] == 'lead' and enrollment.anchor_at <= m['timestamp'] <= now), None)
    if response:
        latest = enrollment.deliveries.filter(status__in=CONFIRMED, sent_at__lte=response['timestamp']).order_by('-sent_at').first()
        # Human intervention breaks exclusive template attribution.
        if latest and response['timestamp'] <= latest.sent_at + timedelta(hours=24):
            if not any(m['sender'] == 'agent' and latest.sent_at < m['timestamp'] < response['timestamp'] for m in messages):
                latest.response_at = response['timestamp']
                latest.save(update_fields=['response_at'])
        stop(enrollment, 'El cliente respondió; requiere atención del agente.', response['timestamp'])
        return False
    _, reason = eligibility(enrollment.policy, snapshot, now)
    if reason:
        stop(enrollment, reason)
        return False
    if snapshot.get('agent_id') != enrollment.context.get('agent_id'):
        stop(enrollment, 'Cambió el agente responsable.')
        return False
    known_ids = set(enrollment.deliveries.exclude(provider_message_id='').values_list('provider_message_id', flat=True))
    if any(m['sender'] in ('agent', 'bot') and m['timestamp'] > enrollment.anchor_at and str(m.get('id', '')) not in known_ids for m in messages):
        stop(enrollment, 'Intervención externa posterior al contacto; revisar seguimiento.')
        return False
    return True


def claim(delivery_id, snapshot, now):
    """Serialize quota reservations across campaigns/contacts; one in-flight send."""
    RemarketingRuntime.objects.get_or_create(pk=1)
    with transaction.atomic():
        RemarketingRuntime.objects.select_for_update().get(pk=1)
        delivery = RemarketingDelivery.objects.select_for_update().select_related('enrollment__campaign').get(pk=delivery_id)
        enrollment = delivery.enrollment
        campaign = enrollment.campaign
        if delivery.status != 'pending' or delivery.due_at > now or enrollment.status != 'active' or campaign.status != 'active':
            return None
        if snapshot.get('contact_key') != enrollment.contact_key:
            stop(enrollment, 'La identidad del contacto cambió.')
            return None
        if not reconcile(enrollment, snapshot, now):
            return None
        policy = enrollment.policy
        local = now.astimezone(LIMA)
        if local.weekday() not in policy['weekdays'] or not policy['start_hour'] <= local.hour < policy['end_hour']:
            delivery.reason = 'Esperando horario permitido.'
            delivery.save(update_fields=['reason'])
            return None
        # Recovery never bursts overdue steps: retain only the latest due step.
        latest_due = enrollment.deliveries.filter(status='pending', due_at__lte=now).order_by('-due_at').first()
        if latest_due.pk != delivery.pk:
            delivery.status, delivery.reason = 'skipped', 'Paso superado; se conserva el último paso vencido.'
            delivery.save(update_fields=['status', 'reason'])
            return None
        recent = RemarketingDelivery.objects.filter(status__in=RESERVED, attempted_at__gt=now-timedelta(hours=24))
        contact = recent.filter(enrollment__contact_key=enrollment.contact_key)
        day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        used = recent.filter(enrollment__campaign=campaign)
        blocked = (
            used.filter(attempted_at__gte=day_start).count() >= campaign.daily_limit
            or used.filter(attempted_at__gt=now-timedelta(hours=1)).count() >= campaign.hourly_limit
            or contact.count() >= campaign.contact_limit
            or contact.filter(status__in=['sending', 'uncertain']).exists()
            or contact.filter(attempted_at__gt=now-timedelta(minutes=max(policy['min_gap_minutes'], campaign.min_gap_minutes))).exists()
        )
        if blocked:
            delivery.reason = 'Esperando cupo, separación mínima o conciliación de envío.'
            delivery.save(update_fields=['reason'])
            return None
        delivery.status, delivery.attempted_at, delivery.reason = 'sending', now, ''
        delivery.save(update_fields=['status', 'attempted_at', 'reason'])
        return delivery


def record_result(delivery_id, result, now=None):
    now = now or timezone.now()
    ranks = {'accepted': 1, 'sent': 2, 'delivered': 3}
    with transaction.atomic():
        item = RemarketingDelivery.objects.select_for_update().get(pk=delivery_id)
        if not isinstance(result, dict):
            raise ValueError('Confirmación inválida.')
        status = result.get('status')
        provider_id = str(result.get('message_id') or '')
        if status == 'failed' and result.get('definitely_not_sent') is True:
            if item.status in ['sending', 'uncertain', 'accepted']:
                item.status, item.reason = 'failed', 'El proveedor confirmó que no se envió.'
                item.save(update_fields=['status', 'reason'])
            return
        if status not in ranks or not provider_id or len(provider_id) > 200:
            if item.status == 'sending':
                item.status, item.reason = 'uncertain', 'Sin confirmación válida; conciliar antes de reintentar.'
                item.save(update_fields=['status', 'reason'])
            return
        if item.status not in ['sending', 'uncertain', *ranks]:
            raise ValueError('El paso no fue enviado.')
        if item.provider_message_id and item.provider_message_id != provider_id:
            raise ValueError('El identificador del proveedor no coincide.')
        if ranks.get(item.status, 0) > ranks[status]:
            return
        sent_at = as_time(result['sent_at']) if status in CONFIRMED else None
        delivered_at = as_time(result['delivered_at']) if status == 'delivered' else None
        if sent_at and (sent_at > now or sent_at < item.attempted_at-timedelta(minutes=1)):
            raise ValueError('Fecha de envío inválida.')
        if delivered_at and (delivered_at < sent_at or delivered_at > now):
            raise ValueError('Fecha de entrega inválida.')
        item.status, item.provider_message_id, item.reason = status, provider_id, ''
        item.sent_at = sent_at or item.sent_at
        item.delivered_at = delivered_at or item.delivered_at
        item.save(update_fields=['status', 'provider_message_id', 'reason', 'sent_at', 'delivered_at'])


def dispatch(delivery_id, gateway, now=None):
    fixed_now = now
    delivery = RemarketingDelivery.objects.select_related('enrollment').get(pk=delivery_id)
    try:
        snapshot = gateway.snapshot(delivery.enrollment.source_lead_id)
        if not isinstance(snapshot, dict):
            raise ValueError('Fuente inválida.')
        now = fixed_now or timezone.now()
        observed = as_time(snapshot.get('observed_at'))
        if not 0 <= (now-observed).total_seconds() <= 60 or snapshot.get('contact_allowed') is not True:
            raise ValueError('La fuente no confirma datos actuales y contacto permitido.')
        if int(snapshot.get('lead_id', 0)) != delivery.enrollment.source_lead_id:
            raise ValueError('Lead incorrecto en la fuente.')
        if not isinstance(snapshot.get('version'), str) or not snapshot['version']:
            raise ValueError('Falta versión de la conversación para revalidación atómica.')
        if any(not isinstance(snapshot.get(field), bool) for field in ('closed', 'visit_intent', 'visit_scheduled')):
            raise ValueError('Falta confirmar cierre e intención/agenda de visita.')
        claimed = claim(delivery_id, snapshot, now)
    except (ValueError, TypeError, KeyError):
        RemarketingDelivery.objects.filter(pk=delivery_id, status='pending').update(reason='No se pudo validar conversación actual; envío retenido.')
        return False
    if not claimed:
        return False
    try:
        result = gateway.send(claimed, snapshot)
        record_result(claimed.pk, result, fixed_now or timezone.now())
    except Exception:
        # The provider may have sent the message; NEVER blindly resend a timeout.
        RemarketingDelivery.objects.filter(pk=claimed.pk, status='sending').update(status='uncertain', reason='Error de transporte; requiere conciliación, no reintento automático.')
    return True
