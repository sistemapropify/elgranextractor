from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import uuid
from lead_intelligence.control_engine import observe, policy, create_obligation
from lead_intelligence.control_notifications import tick, send_pending
from lead_intelligence.control_source import source_page, source_snapshot
from lead_intelligence.control_digest import daily_digest
from lead_intelligence.models import LeadControlState, LeadControlPolicy


class Command(BaseCommand):
    help = 'Sincroniza cartera y controla plazos; --notify habilita transporte según configuración.'

    def add_arguments(self, parser):
        parser.add_argument('--lead-id', type=int)
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--tick-only', action='store_true')
        parser.add_argument('--notify', action='store_true')

    def handle(self, *args, **options):
        settings = policy()
        if not settings.active_statuses or not settings.closed_statuses:
            raise CommandError('Configura los estados activos/cerrados en Control → Reglas antes de sincronizar.')
        limit = options['limit']
        if not 1 <= limit <= 1000:
            raise CommandError('limit debe estar entre 1 y 1000.')
        if options['tick_only']:
            # Deadlines keep running even while a long CRM scan holds its lease.
            self.process(settings, options, limit, '')
            return
        token = uuid.uuid4().hex
        with transaction.atomic():
            locked = LeadControlPolicy.objects.select_for_update().get(pk=settings.pk)
            if locked.scan_lease_until and locked.scan_lease_until > timezone.now():
                self.stdout.write('Ya hay una revisión de control en curso.')
                return
            locked.scan_lease_token, locked.scan_lease_until = token, timezone.now()+timedelta(minutes=5)
            locked.save(update_fields=['scan_lease_token', 'scan_lease_until'])
        try:
            self.process(settings, options, limit, token)
        finally:
            LeadControlPolicy.objects.filter(pk=settings.pk, scan_lease_token=token).update(scan_lease_until=None, scan_lease_token='')

    def process(self, settings, options, limit, token):
        failures, updated = 0, 0
        if not options['tick_only']:
            page_ok = True
            try:
                page = [options['lead_id']] if options['lead_id'] else source_page(settings.scan_after_id, limit)
            except Exception:
                page, page_ok = [], False
                self.stderr.write('No se pudo descubrir cartera; se revisan los leads ya conocidos.')
            # New/old leads discovered in pages. Already monitored active leads
            # are revisited regardless of creation date or page cursor.
            ids = set(page)
            if not options['lead_id']:
                ids.update(LeadControlState.objects.filter(active=True).values_list('source_lead_id', flat=True))
            for lead_id in sorted(ids):
                if not LeadControlPolicy.objects.filter(pk=settings.pk, scan_lease_token=token, scan_lease_until__gt=timezone.now()).update(scan_lease_until=timezone.now()+timedelta(minutes=5)):
                    self.stderr.write('La revisión perdió su reserva; otro trabajador podrá continuar.')
                    return
                try:
                    observe(source_snapshot(lead_id), settings)
                    updated += 1
                except Exception:
                    state, _ = LeadControlState.objects.get_or_create(source_lead_id=lead_id)
                    LeadControlState.objects.filter(pk=state.pk).update(quality='unknown', last_error='No se pudo consultar el CRM. Se conserva la última información conocida.')
                    if state.active and not state.obligations.filter(kind='data', action__status='pending').exists():
                        at = timezone.now()
                        create_obligation(state, 'data', at, at.isoformat(), settings, {'type': 'source_unavailable'})
                    failures += 1
                    self.stderr.write(f'Lead {lead_id}: lectura pendiente de recuperar.')
            if not options['lead_id'] and page_ok:
                LeadControlPolicy.objects.filter(pk=settings.pk).update(scan_after_id=page[-1] if page else 0)
        evaluated = tick()
        result = send_pending(limit) if options['notify'] else {'transport': 'disabled'}
        daily_digest(send=options['notify'])
        self.stdout.write(f'Actualizados: {updated}; errores: {failures}; pendientes revisados: {evaluated}; avisos: {result}')
