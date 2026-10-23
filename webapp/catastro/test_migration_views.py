import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from . import migration_views


class MigrationViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(pk=1, username='admin', is_active=True,
                                    is_authenticated=True, is_superuser=True,
                                    is_staff=False)

    @patch('catastro.migration_views.R2')
    @patch('catastro.migration_views.Gateway')
    @patch('catastro.migration_views.migration_runner.job', return_value={'status': 'idle'})
    @patch('catastro.migration_views.geollaqta_bulk.migration_status')
    def test_status_reports_r2_and_master_counts(self, status, job, gateway, cloud):
        status.return_value = {'ubigeo': '040126', 'source_lots': 5240,
                               'linked_lots': 100, 'pending_lots': 5140}
        request = self.factory.get('/catastro/api/maestro/migracion/',
                                   {'ubigeo': '040126'})
        request.current_user = self.user
        response = migration_views.status(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['pending_lots'], 5140)
        self.assertEqual(json.loads(response.content)['job']['status'], 'idle')
        status.assert_called_once()

    @patch('catastro.migration_views.R2')
    @patch('catastro.migration_views.Gateway')
    @patch('catastro.migration_views.geollaqta_bulk.migrate_pending')
    def test_migrate_runs_a_bounded_batch(self, migrate, gateway, cloud):
        migrate.return_value = {'ubigeo': '040126', 'processed_lots': 20,
                                'linked_lots': 120, 'pending_lots': 5120,
                                'done': False}
        request = self.factory.post(
            '/catastro/api/maestro/migracion/ejecutar/',
            data=json.dumps({'ubigeo': '040126', 'limit': 20}),
            content_type='application/json')
        request.current_user = self.user
        request._dont_enforce_csrf_checks = True
        response = migration_views.migrate(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['processed_lots'], 20)
        self.assertEqual(migrate.call_args.args[1:3], ('040126', 20))

    @patch('catastro.migration_views.migration_runner.start')
    def test_background_start_returns_accepted_job(self, start):
        start.return_value = {'started': True, 'job': {'status': 'running', 'id': 'job-1'}}
        request = self.factory.post(
            '/catastro/api/maestro/migracion/iniciar/',
            data=json.dumps({'ubigeo': '040126', 'batch_size': 20}),
            content_type='application/json')
        request.current_user = self.user
        request._dont_enforce_csrf_checks = True
        response = migration_views.start(request)
        self.assertEqual(response.status_code, 202)
        self.assertTrue(json.loads(response.content)['started'])
        start.assert_called_once_with('040126', 'admin', 20)

    @patch('catastro.migration_views.Gateway')
    @patch('catastro.migration_views.migration_runner.job')
    def test_background_job_status_is_exposed(self, job, gateway):
        job.return_value = {'status': 'running', 'linked_lots': 21, 'pending_lots': 5219}
        request = self.factory.get('/catastro/api/maestro/migracion/estado/',
                                   {'ubigeo': '040126'})
        request.current_user = self.user
        response = migration_views.job(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['job']['pending_lots'], 5219)
