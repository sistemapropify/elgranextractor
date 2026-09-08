import asyncio
import copy
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from django.utils import timezone
from colas.scraping_tasks import _release_for_shutdown
from ingestas.lifecycle import start_or_resume_portal_run
from ingestas.models import ScrapingJob, PropiedadesCompetencia, ScrapingHistoryRepair
from ingestas.scraping_history import propose, apply_plan, rollback_batch
from scrapi.contracts import ScrapingInterrupted
from scrapi.paged_engine import prepare_detail


class HistoryRepairTests(TestCase):
    def prop(self, key='1'):
        return PropiedadesCompetencia.objects.create(fuente='urbania', id_origen=key,
            precio_usd=230, area_m2=1285, datos_crudos={'ID': key, 'Precio': 'USD 230,000',
                'Caracteristicas': '128.5 m²', 'Titulo': 'Casa en venta'})

    def test_dry_run_apply_and_idempotent_rollback(self):
        prop = self.prop()
        plan = [propose(prop)]
        self.assertEqual(apply_plan(plan)['count'], 1)
        self.assertFalse(ScrapingHistoryRepair.objects.exists())
        prop.refresh_from_db()
        self.assertEqual(prop.area_m2, Decimal('1285'))
        result = apply_plan(plan, apply=True)
        prop.refresh_from_db()
        self.assertEqual(prop.area_m2, Decimal('128.50'))
        self.assertEqual(prop.precio_usd, Decimal('230000'))
        self.assertEqual(rollback_batch(result['batch'])['count'], 1)
        rollback_batch(result['batch'], apply=True)
        prop.refresh_from_db()
        self.assertEqual(prop.area_m2, Decimal('1285'))
        self.assertEqual(rollback_batch(result['batch'], apply=True)['count'], 0)

    def test_stale_plan_rolls_back_entire_batch(self):
        first, second = self.prop('1'), self.prop('2')
        plan = [propose(first), propose(second)]
        PropiedadesCompetencia.objects.filter(pk=second.pk).update(precio_usd=999)
        with self.assertRaisesRegex(ValueError, 'cambiaron'):
            apply_plan(plan, apply=True)
        first.refresh_from_db()
        self.assertEqual(first.precio_usd, Decimal('230'))
        self.assertFalse(ScrapingHistoryRepair.objects.exists())

    def test_tampered_plan_cannot_inject_an_arbitrary_price(self):
        plan = [propose(self.prop())]
        plan[0]['changes']['precio_usd']['after'] = 42
        with self.assertRaises(ValueError):
            apply_plan(plan, apply=True)

    def test_rollback_preserves_subsequent_scraper_data(self):
        prop = self.prop()
        result = apply_plan([propose(prop)], apply=True)
        PropiedadesCompetencia.objects.filter(pk=prop.pk).update(precio_usd=240000)
        with self.assertRaisesRegex(ValueError, 'no se sobrescribirá'):
            rollback_batch(result['batch'], apply=True)
        self.assertIsNone(ScrapingHistoryRepair.objects.get().rolled_back_at)

    def test_wrong_raw_identity_never_proposes_correction(self):
        prop = self.prop()
        prop.datos_crudos['ID'] = 'other'
        self.assertIsNone(propose(prop))


class WorkerShutdownTests(TestCase):
    @override_settings(SCRAPING_EXECUTION_MODE='external')
    def test_resume_after_paused_worker_shutdown_dispatches_again(self):
        from ingestas.views import ScrapingControlView
        job = ScrapingJob.objects.create(estado='paused', execution_token=None)
        request = RequestFactory().post('/ingestas/scraping/control/', {'action': 'resume', 'job_id': job.pk})
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('ingestas.views._launch_scraping_job', return_value='external') as launch:
            response = ScrapingControlView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        launch.assert_called_once_with(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'idle')

    def test_live_paused_worker_resumes_without_second_dispatch(self):
        from ingestas.views import ScrapingControlView
        job = ScrapingJob.objects.create(estado='paused', execution_token=uuid.uuid4(),
            lease_expires_at=timezone.now()+timedelta(seconds=180))
        request = RequestFactory().post('/ingestas/scraping/control/', {'action': 'resume', 'job_id': job.pk})
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('ingestas.views._launch_scraping_job') as launch:
            response = ScrapingControlView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        launch.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.estado, 'running')

    def test_shutdown_preserves_checkpoint_and_releases_claim(self):
        token = uuid.uuid4()
        job = ScrapingJob.objects.create(estado='running', execution_token=token,
            lease_expires_at=timezone.now() + timedelta(seconds=180),
            parametros={'checkpoints': {'urbania': 12}})
        _release_for_shutdown(job.pk, token)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'idle')
        self.assertIsNone(job.execution_token)
        self.assertEqual(job.parametros['checkpoints']['urbania'], 12)
        self.assertEqual(job.logs.get().evento, 'worker.stopping')

    def test_old_owner_cannot_release_or_start_a_replacement(self):
        old = uuid.uuid4()
        job = ScrapingJob.objects.create(estado='running', execution_token=old)
        current = uuid.uuid4()
        ScrapingJob.objects.filter(pk=job.pk).update(execution_token=current)
        _release_for_shutdown(job.pk, old)
        with self.assertRaises(ScrapingInterrupted):
            start_or_resume_portal_run(job, 'urbania')
        job.refresh_from_db()
        self.assertEqual(job.execution_token, current)
        self.assertFalse(job.ejecuciones_portal.exists())


class DetailRecoveryTests(IsolatedAsyncioTestCase):
    async def test_transient_failure_retries_and_normalizes(self):
        events = []
        async def emit(**event):
            events.append(event)
        raw = {'ID': '1', 'Precio': 'USD 230,000', 'Caracteristicas': '128.5 m²'}
        with patch('scrapi.paged_engine.enrich', AsyncMock(side_effect=[RuntimeError('timeout'), None])) as enrich, patch('scrapi.paged_engine.asyncio.sleep', AsyncMock()):
            row = await prepare_detail('urbania', None, SimpleNamespace(url='https://urbania.pe/item/1'), raw, emit)
        self.assertEqual(enrich.await_count, 2)
        self.assertEqual(row['area_m2'], 128.5)
        self.assertEqual(events[1]['event'], 'detail.retry')

    async def test_cancel_never_retries(self):
        emit = AsyncMock(side_effect=ScrapingInterrupted('stopped'))
        with patch('scrapi.paged_engine.enrich', AsyncMock()) as enrich:
            with self.assertRaises(ScrapingInterrupted):
                await prepare_detail('urbania', None, None, {'ID': '1'}, emit)
        enrich.assert_not_awaited()


class PendingReplayTests(SimpleTestCase):
    def test_failed_pending_detail_does_not_starve_later_candidate(self):
        from scrapi.paged_engine import run_paged
        page = SimpleNamespace(set_viewport_size=AsyncMock())
        browser = SimpleNamespace(new_page=AsyncMock(return_value=page))
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=browser)
        context.__aexit__ = AsyncMock(return_value=False)
        state = {'pending': [{'id': '1', 'raw': {'ID': '1'}}, {'id': '2', 'raw': {'ID': '2'}}],
                 'discovery': {'complete': True, 'stop_reason': 'next_disabled', 'unique_ids': 2}}
        saved, events = [], []
        def save(rows):
            saved.extend(rows)
            return {'total': len(saved)}
        def progress(payload):
            events.append(payload)
            return True
        with patch('camoufox.async_api.AsyncCamoufox', return_value=context), \
             patch('scrapi.camoufox_launcher.camoufox_kwargs', return_value={}), \
             patch('scrapi.paged_engine.guarded_navigation', AsyncMock()), \
             patch('scrapi.paged_engine.prepare_detail', AsyncMock(side_effect=[RuntimeError('gone'), {'id_origen': '2'}])):
            result = run_paged('urbania', source_url='https://urbania.pe/buscar/casas',
                               resume_state=state, progress_callback=progress, batch_callback=save)
        self.assertEqual(saved, [{'id_origen': '2'}])
        self.assertEqual(result.discovery.details_failed, 1)
        self.assertTrue(result.discovery.complete)  # Coverage evidence remains; pending still blocks finalization.
        self.assertTrue(any(e.get('candidate_error', {}).get('id') == '1' for e in events))

    @override_settings(ALLOWED_HOSTS=['testserver'])
    def test_anonymous_requests_cannot_read_logs_or_status(self):
        from django.contrib.auth.models import AnonymousUser
        from ingestas.views import ScrapingStreamView, ScrapingStatusView
        for view in (ScrapingStreamView, ScrapingStatusView):
            request = RequestFactory().get('/ingestas/scraping/stream/1/?poll=1')
            request.user = AnonymousUser()
            self.assertEqual(view.as_view()(request, job_id=1).status_code, 302)


class WorkerHealthTests(TestCase):
    def test_another_host_cannot_mask_missing_worker(self):
        from ingestas.models import ScrapingWorker
        from ingestas.scraping_health import worker_health
        ScrapingWorker.objects.create(identity='other', heartbeat_at=timezone.now())
        self.assertTrue(worker_health()['ready'])
        self.assertFalse(worker_health('this-host')['ready'])

    def test_metrics_report_expired_lease_and_no_worker_without_writes(self):
        import io
        import json
        from django.core.management import call_command
        job = ScrapingJob.objects.create(estado='running', lease_expires_at=timezone.now()-timedelta(seconds=1))
        output = io.StringIO()
        call_command('scraping_metrics', stdout=output)
        report = json.loads(output.getvalue())
        self.assertIn('execution.lease_expired', report['issues'])
        self.assertIn('worker.unavailable', report['issues'])
        job.refresh_from_db()
        self.assertEqual(job.estado, 'running')
