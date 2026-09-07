from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from lead_intelligence.models import RemarketingCampaign, RemarketingDelivery, RemarketingEnrollment, RemarketingRuntime
from lead_intelligence.remarketing_engine import dispatch, enroll, reconcile
from lead_intelligence.remarketing_gateway import RemarketingGateway, crm_snapshot, discover_lead_ids


class Command(BaseCommand):
    help = 'Inscribe leads y procesa pasos de remarketing. Sin --send solo programa; nunca envía.'

    def add_arguments(self, parser):
        parser.add_argument('--lead-id', type=int)
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--send', action='store_true')

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 1000:
            raise CommandError('limit debe estar entre 1 y 1000.')
        gateway = None
        if options['send']:
            try:
                gateway = RemarketingGateway()
            except ValueError as exc:
                raise CommandError(str(exc))
        campaigns = list(RemarketingCampaign.objects.filter(status='active').prefetch_related('steps'))
        runtime, _ = RemarketingRuntime.objects.get_or_create(pk=1)
        ids = ([options['lead_id']] if options['lead_id'] else discover_lead_ids(runtime.scan_after_id, limit)) if campaigns else []
        inspected, failures = 0, 0
        for lead_id in ids:
            try:
                snapshot = crm_snapshot(lead_id)
                for campaign in campaigns:
                    enroll(campaign, snapshot)
                inspected += 1
            except Exception:
                # Do not print phone numbers, message bodies or provider credentials.
                failures += 1
                self.stderr.write(f'Lead {lead_id}: no se pudo verificar/inscribir; se revisará en el siguiente barrido.')
        if not options['lead_id']:
            RemarketingRuntime.objects.filter(pk=1).update(scan_after_id=ids[-1] if ids else 0)
        # Reconcile open episodes even when there is no due delivery (e.g. last step sent).
        active = RemarketingEnrollment.objects.filter(
            Q(status='active') | Q(deliveries__sent_at__gte=timezone.now()-timedelta(hours=24))
        ).distinct().order_by('pk')
        if options['lead_id']:
            active = active.filter(source_lead_id=options['lead_id'])
        # Entire active set: limiting to the oldest would permanently starve newer cases.
        for enrollment in active.iterator(chunk_size=100):
            try:
                snapshot = crm_snapshot(enrollment.source_lead_id)
                # CRM cancellation is conservative; only the gateway authorizes delivery.
                reconcile(enrollment, snapshot, timezone.now())
            except Exception:
                failures += 1
        pending = RemarketingDelivery.objects.filter(status='pending', due_at__lte=timezone.now(), enrollment__status='active', enrollment__campaign__status='active').order_by('due_at')
        if options['lead_id']:
            pending = pending.filter(enrollment__source_lead_id=options['lead_id'])
        attempts = 0
        if gateway:
            # Use the full due set: out-of-hours/capped rows must not starve other campaigns.
            for delivery_id in pending.values_list('pk', flat=True).iterator(chunk_size=100):
                if dispatch(delivery_id, gateway):
                    attempts += 1
                    if attempts >= limit:
                        break
        self.stdout.write(f'Leads revisados: {inspected}; errores: {failures}; intentos: {attempts}; pendientes vencidos: {pending.count()}.')
