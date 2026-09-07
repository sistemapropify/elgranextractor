"""Transactional notification outbox with internal, SMTP and Firebase channels."""
import json
import os
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.core.mail import EmailMessage
from django.utils import timezone

from .models import LeadObligation, LeadControlMember, LeadControlNotice, LeadControlEvent, RecommendedAction
from .control_engine import policy, active_since
from .control_calendar import add_minutes, business_seconds
from .remarketing_gateway import config


def enabled(name):
    return str(config(name)).lower() in ('true', '1')


def member_devices(member):
    mobile_id = member.mobile_identity_id or (member.identity_id if member.identity_type == 'propify' else '')
    if not mobile_id:
        return []
    from prospects.models import MobileNotificationDevice
    return list(MobileNotificationDevice.objects.filter(active=True, user__propify_user_id=mobile_id))


def recipients(item, level, now):
    owner = LeadControlMember.objects.filter(source_user_id=item.action.source_assigned_user_id, active=True).first() if item.action.source_assigned_user_id is not None else None
    if level == 'agent' and owner and (not owner.away_until or owner.away_until <= now):
        return [owner]
    if level in ('agent', 'supervisor') and owner and owner.supervisor and owner.supervisor.active:
        return [owner.supervisor]
    return list(LeadControlMember.objects.filter(active=True, role='manager'))


def queue_notice(item, level, now):
    people = recipients(item, level, now)
    if not people:
        LeadControlNotice.objects.get_or_create(dedupe_key=f'{item.pk}:{level}:unroutable', defaults={'obligation': item, 'level': level, 'channel': 'internal', 'status': 'unroutable', 'last_error': 'Configura un responsable y su ruta de supervisión/gerencia.'})
        return
    item.notices.filter(level=level, status='unroutable').update(status='cancelled')
    for person in people:
        base = f'{item.pk}:{level}:{person.pk}'
        LeadControlNotice.objects.get_or_create(dedupe_key=f'{base}:internal', defaults={'obligation': item, 'recipient': person, 'level': level, 'channel': 'internal', 'status': 'available'})
        if person.email:
            LeadControlNotice.objects.get_or_create(dedupe_key=f'{base}:email', defaults={'obligation': item, 'recipient': person, 'level': level, 'channel': 'email', 'destination': person.email})
        for device in member_devices(person):
            LeadControlNotice.objects.get_or_create(dedupe_key=f'{base}:push:{device.pk}', defaults={'obligation': item, 'recipient': person, 'level': level, 'channel': 'push', 'device_id': device.pk})


def tick(now=None):
    now, settings = now or timezone.now(), policy()
    count = 0
    # Batch unroutable notices while the initial directory is still empty.
    no_directory = not LeadControlMember.objects.filter(active=True).exists()
    existing = set(LeadControlNotice.objects.values_list('dedupe_key', flat=True)) if no_directory else set()
    pending_notices, critical = [], []
    rescues = set(LeadControlEvent.objects.filter(kind='rescue_requested', obligation__action__status='pending').values_list('obligation_id', flat=True))
    def enqueue(item, level):
        if not no_directory:
            queue_notice(item, level, now)
            return
        key = f'{item.pk}:{level}:unroutable'
        if key not in existing:
            pending_notices.append(LeadControlNotice(dedupe_key=key, obligation=item, level=level, channel='internal', status='unroutable', last_error='Configura un responsable y su ruta de supervisión/gerencia.'))
            existing.add(key)
    items = LeadObligation.objects.filter(action__status='pending', lead__active=True)
    cutoff = active_since()
    if cutoff:
        items = items.filter(lead__entered_at__gte=cutoff)
    for item in items.select_related('lead', 'action').iterator(chunk_size=200):
        stale = item.lead.observed_at is None or now-item.lead.observed_at > timedelta(minutes=settings.stale_minutes)
        if stale or item.lead.quality != 'valid':
            enqueue(item, 'data')
            continue
        due = item.action.due_at
        warning = add_minutes(item.started_at, business_seconds(item.started_at, due, item.calendar)/60*0.8, item.calendar)
        if now >= warning:
            enqueue(item, 'agent')
        if now >= item.supervisor_at:
            enqueue(item, 'supervisor')
        if now >= item.manager_at:
            enqueue(item, 'manager')
            if item.action.priority != 'critical':
                critical.append(item.action_id)
        if item.kind == 'visit':
            enqueue(item, 'visit')
        if item.pk in rescues:
            enqueue(item, 'supervisor')
        count += 1
    LeadControlNotice.objects.bulk_create(pending_notices, batch_size=50)
    for offset in range(0, len(critical), 400):
        RecommendedAction.objects.filter(pk__in=critical[offset:offset+400], status='pending').update(priority='critical')
    return count


def notification_text(notice):
    item = notice.obligation
    if notice.level == 'data':
        return 'Control de leads: datos por verificar', f'Lead #{item.lead.source_lead_id}: la fuente necesita revisión. Consulta el centro de control.'
    title = 'Nueva intención de visita' if item.kind == 'visit' else 'Lead requiere atención'
    return title, f'Lead #{item.lead.source_lead_id}: {item.action.title}. Revisa el pendiente y su plazo en Propitools o PROMETEO.'


def send_firebase(device, title, body, item_id):
    """HTTP v1 supports registered FIDs and legacy registration tokens."""
    import google.auth
    from google.auth.transport.requests import Request
    raw_credentials = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
    if raw_credentials:
        from google.oauth2 import service_account
        info = json.loads(raw_credentials)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/firebase.messaging']
        )
        default_project = info.get('project_id')
    else:
        credentials, default_project = google.auth.default(scopes=['https://www.googleapis.com/auth/firebase.messaging'])
    project = config('LEAD_CONTROL_FIREBASE_PROJECT_ID') or default_project
    if not project or not re.fullmatch(r'[A-Za-z0-9_-]+', project):
        raise ValueError('Proyecto Firebase no configurado.')
    credentials.refresh(Request())
    target = 'fid' if device.target_type == 'fid' else 'token'
    response = requests.post(f'https://fcm.googleapis.com/v1/projects/{project}/messages:send', headers={'Authorization': f'Bearer {credentials.token}'}, json={'message': {
        target: device.registration_id,
        'notification': {'title': title, 'body': body},
        'data': {'destination': 'crm_alerts', 'alert_id': str(item_id)},
        'android': {'priority': 'high', 'ttl': '3600s', 'notification': {'channel_id': 'crm_visit_intent', 'tag': f'control-{item_id}'}},
    }}, timeout=(5, 20), allow_redirects=False)
    if response.status_code != 200:
        if response.status_code == 404 and any(entry.get('errorCode') == 'UNREGISTERED' for entry in response.json().get('error', {}).get('details', [])):
            device.active = False
            device.save(update_fields=['active'])
        raise ValueError('Firebase no confirmó el envío.')
    message_id = response.json().get('name')
    if not message_id:
        raise ValueError('Sin identificador de Firebase.')
    return message_id


def send_pending(limit=100, push_sender=send_firebase, now=None):
    """Never interprets SMTP/FCM acceptance as delivery or reading."""
    result = {'accepted': 0, 'uncertain': 0, 'cancelled': 0}
    now = now or timezone.now()
    stale_before = now-timedelta(minutes=policy().stale_minutes)
    channels = [channel for channel in ('email', 'push') if enabled(f'LEAD_CONTROL_{channel.upper()}_ENABLED')]
    queryset = LeadControlNotice.objects.filter(status='pending', channel__in=channels).order_by('created_at')
    for item_id in list(queryset.values_list('pk', flat=True)[:limit]):
        with transaction.atomic():
            notice = LeadControlNotice.objects.select_for_update().select_related('obligation__action', 'obligation__lead', 'recipient').get(pk=item_id)
            if notice.status != 'pending':
                continue
            if not enabled('LEAD_CONTROL_EMAIL_ENABLED' if notice.channel == 'email' else 'LEAD_CONTROL_PUSH_ENABLED'):
                continue
            state = notice.obligation.lead
            stale = not state.observed_at or state.observed_at < stale_before or state.quality != 'valid'
            if notice.level != 'data' and stale:
                continue
            if notice.level == 'data' and not stale:
                notice.status = 'cancelled'
                notice.save(update_fields=['status'])
                continue
            if notice.obligation.action.status != 'pending' or not notice.obligation.lead.active or not notice.recipient or not notice.recipient.active:
                notice.status = 'cancelled'
                notice.save(update_fields=['status'])
                result['cancelled'] += 1
                continue
            # Revalidate scope: reassigned leads must not notify their former agents.
            from .control_access import ControlAccess
            if not ControlAccess(member=notice.recipient).states().filter(pk=notice.obligation.lead_id).exists():
                notice.status = 'cancelled'
                notice.save(update_fields=['status'])
                continue
            notice.status, notice.attempts = 'sending', notice.attempts+1
            notice.save(update_fields=['status', 'attempts'])
        try:
            title, body = notification_text(notice)
            if notice.channel == 'email':
                if notice.destination != notice.recipient.email:
                    raise ValueError('El destinatario cambió; revisar ruta.')
                link_base = config('LEAD_CONTROL_PUBLIC_URL').rstrip('/')
                if link_base.startswith('https://'):
                    body += f'\n{link_base}/analisis-crm/control/leads/{notice.obligation.lead.source_lead_id}/'
                if EmailMessage(title, body, to=[notice.destination]).send() != 1:
                    raise ValueError('SMTP no confirmó aceptación.')
                provider_id = 'smtp-accepted'
            else:
                devices = {d.pk: d for d in member_devices(notice.recipient)}
                if notice.device_id not in devices:
                    raise ValueError('El dispositivo ya no pertenece al destinatario.')
                provider_id = push_sender(devices[notice.device_id], title, body, notice.obligation_id)
            LeadControlNotice.objects.filter(pk=notice.pk, status='sending').update(status='accepted', sent_at=timezone.now(), provider_id=provider_id)
            result['accepted'] += 1
        except Exception:
            LeadControlNotice.objects.filter(pk=notice.pk, status='sending').update(status='uncertain', last_error='Sin confirmación fiable; revisar configuración/proveedor antes de reintentar.')
            result['uncertain'] += 1
    return result
