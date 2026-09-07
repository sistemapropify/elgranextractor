"""Daily, scoped control snapshots. SMTP acceptance is recorded separately."""
from datetime import timedelta
import hashlib
import json

from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .control_access import ControlAccess
from .control_engine import policy
from .control_metrics import metrics
from .control_notifications import enabled
from .models import LeadControlDigest, LeadControlMember, LeadControlNotice, LeadObligation, LeadControlEvent
from .remarketing_engine import LIMA
from .remarketing_gateway import config


def scope_key(member):
    team = list(member.team.filter(active=True).order_by('pk').values_list('pk', 'source_user_id'))
    return hashlib.sha256(json.dumps([member.pk, member.role, member.source_user_id, team]).encode()).hexdigest()


def daily_digest(now=None, send=False):
    now, rules = now or timezone.now(), policy()
    local = now.astimezone(LIMA)
    if local.hour < rules.digest_hour:
        return 0
    created_count = 0
    for member in LeadControlMember.objects.filter(active=True, role__in=['manager', 'supervisor']):
        existing = LeadControlDigest.objects.filter(recipient=member, day=local.date()).first()
        states = ControlAccess(member=member).states()
        if not existing:
            obligations = LeadObligation.objects.filter(lead__in=states).filter(Q(started_at__gte=now-timedelta(days=30)) | Q(action__status='pending')).select_related('lead', 'action')
            stats = metrics(obligations, now, rules.stale_minutes)
            incidents = LeadControlNotice.objects.filter(obligation__lead__in=states, status__in=['unroutable', 'uncertain', 'failed']).count()
            rescues = LeadControlEvent.objects.filter(lead__in=states, kind__in=['rescue_requested', 'owner_changed'], created_at__gte=local.replace(hour=0, minute=0, second=0, microsecond=0)).count()
            oldest = list(obligations.filter(action__status='pending').order_by('started_at').values('lead__source_lead_id', 'kind', 'started_at', 'action__due_at', 'action__source_assigned_user_id')[:50])
            # Preserve the source time and scope, not a claim of historic blame.
            rows = [{k: v.isoformat() if hasattr(v, 'isoformat') else v for k, v in row.items()} for row in oldest]
            existing, created = LeadControlDigest.objects.get_or_create(recipient=member, day=local.date(), defaults={'payload': {'scope_key': scope_key(member), 'stats': stats, 'integration_incidents': incidents, 'interventions_today': rescues, 'oldest_pending': rows, 'observed_at': now.isoformat()}})
            created_count += created
        if not send or not enabled('LEAD_CONTROL_EMAIL_ENABLED') or not member.email:
            continue
        with transaction.atomic():
            record = LeadControlDigest.objects.select_for_update().get(pk=existing.pk)
            if record.email_status != 'pending':
                continue
            # A manager may have changed role/team since this snapshot was made.
            current = LeadControlMember.objects.get(pk=member.pk)
            if not current.active or current.role not in ('manager', 'supervisor'):
                continue
            record.email_status = 'sending'
            record.save(update_fields=['email_status'])
        try:
            # Do not email lead identities from a previous scope; link opens the
            # current authorized view. The saved report stays local to its owner.
            body = f'Tu resumen de control del {local.date().isoformat()} está disponible en PROMETEO. Revisa pendientes, vencimientos, intervenciones y problemas de entrega.'
            current_items = LeadObligation.objects.filter(lead__in=ControlAccess(member=current).states(), action__status='pending').select_related('lead', 'action')
            current_stats = metrics(current_items, now, rules.stale_minutes)
            body += f"\nSituación actual: {current_stats['open']} pendientes, {current_stats['overdue']} vencidos, {current_stats['escalated']} escalados y {current_stats['unknown']} pendientes con datos por verificar."
            url = config('LEAD_CONTROL_PUBLIC_URL').rstrip('/')
            if url.startswith('https://'):
                body += f'\n{url}/analisis-crm/control/'
            if EmailMessage('Resumen diario de control de leads', body, to=[current.email]).send() != 1:
                raise ValueError('Sin aceptación SMTP.')
            LeadControlDigest.objects.filter(pk=record.pk).update(email_status='accepted', emailed_at=now)
        except Exception:
            LeadControlDigest.objects.filter(pk=record.pk).update(email_status='uncertain', last_error='Revisar SMTP antes de reintentar; no se confirmó aceptación.')
    return created_count
