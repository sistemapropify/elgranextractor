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
    @patch('catastro.migration_views.geollaqta_bulk.migration_status')
    def test_status_reports_r2_and_master_counts(self, status, gateway, cloud):
        status.return_value = {'ubigeo': '040126', 'source_lots': 5240,
                               'linked_lots': 100, 'pending_lots': 5140}
        request = self.factory.get('/catastro/api/maestro/migracion/',
                                   {'ubigeo': '040126'})
        request.current_user = self.user
        response = migration_views.status(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['pending_lots'], 5140)
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
