import json
import os
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from ingestas.models import ScrapingJob, ScrapingWorker, PropiedadesCompetencia
from ingestas.scraping_execution import can_execute, local_worker_status, native_worker_identity
from ingestas.views import ScrapingControlView, _launch_scraping_job


class ExecutionRoutingTests(SimpleTestCase):
    def params(self):
        return {'portales': ['adondevivir'], 'native_verification': True,
                'execution_scope': 'local_interactive', 'execution_host': native_worker_identity()}

    def test_native_job_requires_windows_dedicated_worker_and_matching_host(self):
        params = self.params()
        with patch('ingestas.scraping_execution.os.name', 'posix'), \
             patch.dict(os.environ, {'SCRAPING_LOCAL_NATIVE_WORKER': '1'}):
            self.assertFalse(can_execute(params))
        with patch('ingestas.scraping_execution.os.name', 'nt'), \
             patch.dict(os.environ, {'SCRAPING_LOCAL_NATIVE_WORKER': '0'}):
            self.assertFalse(can_execute(params))
        with patch('ingestas.scraping_execution.os.name', 'nt'), \
             patch.dict(os.environ, {'SCRAPING_LOCAL_NATIVE_WORKER': '1'}):
            self.assertTrue(can_execute(params))
            params['execution_host'] = 'adondevivir-pc:another'
            self.assertFalse(can_execute(params))
        self.assertFalse(can_execute({'execution_scope': 'portable'}, native_only=True))

    @patch('ingestas.views.threading.Thread')
    @patch('colas.scraping_tasks.scraping_task.apply_async')
    def test_native_dispatch_never_starts_cloud_thread_or_celery(self, celery, thread):
        self.assertEqual(_launch_scraping_job(12, execution_params=self.params()), 'local_pc')
        thread.assert_not_called()
        celery.assert_not_called()


class NativeJobIntegrationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.identity = native_worker_identity()

    def worker(self, identity=None, age=0):
        return ScrapingWorker.objects.create(identity=identity or self.identity,
                    heartbeat_at=timezone.now() - timedelta(seconds=age))

    def post(self, **values):
        request = self.factory.post('/ingestas/scraping/control/', values)
        request.user = SimpleNamespace(is_authenticated=True)
        return ScrapingControlView.as_view()(request)

    def test_azure_heartbeat_does_not_hide_disconnected_pc(self):
        self.worker(identity='azure-worker')
        self.assertFalse(local_worker_status()['ready'])
        local = self.worker(age=76)
        self.assertFalse(local_worker_status()['ready'])
        local.heartbeat_at = timezone.now()
        local.save()
        self.assertTrue(local_worker_status()['ready'])
        self.assertFalse(local_worker_status('adondevivir-pc:other')['ready'])

    def test_start_without_pc_does_not_create_a_job(self):
        response = self.post(action='start', portales='adondevivir', urls='{}')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(ScrapingJob.objects.exists())

    @patch('ingestas.views._terminate_scraping_browsers')
    @patch('ingestas.views._acquire_scraping_start_lock', return_value=True)
    @patch('ingestas.views.threading.Thread')
    def test_start_is_assigned_to_live_pc_without_cloud_dispatch(self, thread, lock, terminate):
        self.worker()
        response = self.post(action='start', portales='adondevivir', urls='{}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['execution_mode'], 'local_pc')
        job = ScrapingJob.objects.get()
        self.assertEqual(job.estado, 'idle')
        self.assertEqual(job.parametros['execution_host'], self.identity)
        self.assertTrue(job.parametros['native_verification'])
        thread.assert_not_called()
        terminate.assert_not_called()

    def test_cloud_cannot_claim_native_idle_job(self):
        from colas.scraping_tasks import _run_scraping
        job = ScrapingJob.objects.create(estado='idle', parametros={
            'portales': ['adondevivir'], 'execution_scope': 'local_interactive',
            'execution_host': self.identity, 'native_verification': True})
        with patch('ingestas.scraping_execution.can_execute', return_value=False), \
             patch('colas.scraping_tasks._instanciar_skill') as skill:
            _run_scraping(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'idle')
        self.assertIsNone(job.execution_token)
        skill.assert_not_called()

    @patch('ingestas.views._terminate_scraping_browsers')
    def test_resume_moves_failed_cloud_job_to_pc_without_losing_checkpoint(self, terminate):
        self.worker()
        job = ScrapingJob.objects.create(estado='error', parametros={
            'portales': ['adondevivir'], 'checkpoints': {'adondevivir': 2}})
        response = self.post(action='resume', job_id=job.pk, adon_executor='local_pc')
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.parametros['checkpoints'], {'adondevivir': 2})
        self.assertEqual(job.parametros['execution_host'], self.identity)
        self.assertEqual(job.estado, 'idle')
        terminate.assert_not_called()

    def test_resume_does_not_move_live_cloud_browser(self):
        self.worker()
        job = ScrapingJob.objects.create(estado='paused', parametros={'portales': ['adondevivir']},
                    execution_token=uuid.uuid4(), lease_expires_at=timezone.now() + timedelta(minutes=3))
        response = self.post(action='resume', job_id=job.pk, adon_executor='local_pc')
        self.assertEqual(response.status_code, 409)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'paused')
        self.assertFalse(job.parametros.get('native_verification'))

    def test_resume_rejects_missing_assigned_pc_without_azure_fallback(self):
        self.worker(identity='adondevivir-pc:other')
        job = ScrapingJob.objects.create(estado='error', parametros={
            'portales': ['adondevivir'], 'execution_host': self.identity, 'native_verification': True})
        response = self.post(action='resume', job_id=job.pk)
        self.assertEqual(response.status_code, 503)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'error')

    def test_readiness_endpoint_requires_session(self):
        request = self.factory.get('/ingestas/scraping/control/?local_status=1')
        request.user = SimpleNamespace(is_authenticated=False)
        self.assertEqual(ScrapingControlView.as_view()(request).status_code, 302)

    @patch('ingestas.scraping_execution.can_execute', return_value=True)
    @patch('colas.scraping_tasks._start_portal_heartbeat', return_value=(MagicMock(), MagicMock()))
    @patch('colas.scraping_tasks._instanciar_skill')
    def test_native_job_uses_normal_persistence_and_dashboard_counts(self, instantiate, heartbeat, allowed):
        from colas.scraping_tasks import _run_scraping
        from intelligence.skills.scrapi.paged_skill import execute_paged_skill
        from intelligence.skills.scrapi.db_utils import guardar_propiedades
        from scrapi.contracts import ScrapeRows
        from scrapi.source_config import source_snapshot
        job = ScrapingJob.objects.create(estado='idle', parametros={
            'portales': ['adondevivir'], 'native_verification': True,
            'execution_scope': 'local_interactive', 'execution_host': self.identity,
            'sources': {'adondevivir': source_snapshot('adondevivir')}, 'local_pilot': True})
        skill = SimpleNamespace(name='scraper_adondevivir')
        def runner(max_pages, *, source_url, start_page, progress_callback, batch_callback,
                   resume_state, native_verification=False, listing_only=False):
            self.assertTrue(native_verification)
            self.assertTrue(callable(batch_callback))
            row = {'id_origen': '123456', 'titulo': 'Casa de prueba', 'precio_usd': 125000}
            progress_callback({'candidate_batch': [{'id': '123456', 'raw': row, 'page': 1}]})
            counts = batch_callback([row])
            batch_callback([row])  # Idempotency on the same run and source ID.
            progress_callback({'checkpoint_page': 1, 'processed': counts['total']})
            result = ScrapeRows([row])
            result.discovery.complete = True
            result.discovery.stop_reason = 'next_disabled'
            progress_callback({'discovery': result.discovery.as_dict()})
            return result
        skill.execute = lambda params, context: execute_paged_skill(
            skill, 'adondevivir', runner, guardar_propiedades, params, context)
        instantiate.return_value = skill
        _run_scraping(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.estado, 'completed')
        self.assertEqual(job.procesadas, 1)
        self.assertEqual(job.nuevas, 1)
        self.assertEqual(PropiedadesCompetencia.objects.count(), 1)
        self.assertTrue(job.logs.exists())
        self.assertEqual(job.parametros['checkpoints']['adondevivir'], 1)

    def test_native_recovery_does_not_touch_another_worker(self):
        from ingestas.management.commands.scraping_local_worker import Command
        expired = timezone.now() - timedelta(seconds=5)
        own = ScrapingJob.objects.create(estado='running', lease_expires_at=expired,
            execution_token=uuid.uuid4(), parametros={'native_verification': True,
                'execution_host': self.identity, 'checkpoints': {'adondevivir': 4}})
        other = ScrapingJob.objects.create(estado='running', lease_expires_at=expired,
            execution_token=uuid.uuid4(), parametros={'execution_host': 'azure'})
        with patch('ingestas.management.commands.scraping_local_worker.can_execute',
                   side_effect=lambda params, **kw: params.get('execution_host') == self.identity):
            Command()._recover_native(self.identity)
        own.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(own.estado, 'idle')
        self.assertEqual(own.parametros['checkpoints']['adondevivir'], 4)
        self.assertEqual(other.estado, 'running')
