import json
import time
from unittest.mock import patch

from django.test import SimpleTestCase

from . import migration_runner


class FakeGateway:
    def __init__(self, value=None, revision=10):
        self.value = value
        self.current = revision
        self.calls = []

    def revision(self):
        return self.current

    def read(self, sql, params=()):
        return ([{'value': json.dumps(self.value)}] if self.value else [])

    def call(self, payload):
        self.calls.append(payload)
        self.value = json.loads(payload['changes'][0]['upserts'][1][1])
        self.current += 1
        return {'result': {**payload['result'], 'revision': self.current}}


class MigrationRunnerTests(SimpleTestCase):
    def test_active_lease_prevents_a_second_worker(self):
        gateway = FakeGateway({'status': 'running', 'expires_at': int(time.time()) + 120})
        claimed, value = migration_runner._claim(gateway, '040126', 'admin', 20)
        self.assertFalse(claimed)
        self.assertEqual(value['status'], 'running')
        self.assertEqual(gateway.calls, [])

    def test_expired_or_missing_lease_can_be_claimed(self):
        gateway = FakeGateway({'status': 'running', 'expires_at': int(time.time()) - 1})
        claimed, value = migration_runner._claim(gateway, '040126', 'admin', 20)
        self.assertTrue(claimed)
        self.assertEqual(value['status'], 'running')
        self.assertEqual(value['batch_size'], 20)
        self.assertEqual(len(gateway.calls), 1)

    def test_error_retry_increments_bounded_attempt_counter(self):
        gateway = FakeGateway({'status': 'error', 'attempts': 1,
                               'retryable': True, 'batch_size': 20})
        claimed, value = migration_runner._claim(gateway, '040126', 'admin', 20)
        self.assertTrue(claimed)
        self.assertEqual(value['attempts'], 2)

    def test_only_the_owner_job_can_continue(self):
        gateway = FakeGateway({'id': 'owner', 'status': 'running',
                               'expires_at': int(time.time()) + 120})
        self.assertTrue(migration_runner._owns(gateway, '040126', 'owner'))
        self.assertFalse(migration_runner._owns(gateway, '040126', 'other'))

    @patch('catastro.migration_runner._claim',
           return_value=(True, {'id': 'bounded', 'batch_size': 5}))
    @patch('catastro.migration_runner.Gateway')
    @patch('catastro.migration_runner.threading.Thread')
    def test_start_caps_an_unsafe_batch_before_claim(self, thread, gateway, claim):
        result = migration_runner.start('040126', 'admin', 50)
        self.assertTrue(result['started'])
        self.assertEqual(claim.call_args.args[3], 5)

    @patch('catastro.management.commands.catastro_migration_worker.migration_runner._run')
    @patch('catastro.management.commands.catastro_migration_worker.migration_runner._claim',
           return_value=(True, {'id': 'recovered'}))
    @patch('catastro.management.commands.catastro_migration_worker.migration_runner.job',
           return_value={'status': 'stale', 'batch_size': 20})
    @patch('catastro.management.commands.catastro_migration_worker.Gateway')
    def test_watchdog_recovers_a_stale_migration(self, gateway, job, claim, run):
        from .management.commands.catastro_migration_worker import Command

        self.assertTrue(Command._recover_once('040126'))
        claim.assert_called_once()
        run.assert_called_once_with(
            '040126', 'azure-migration-watchdog', 5, 'recovered')

    @patch('catastro.management.commands.catastro_migration_worker.migration_runner._run')
    @patch('catastro.management.commands.catastro_migration_worker.migration_runner._claim',
           return_value=(True, {'id': 'recovered'}))
    @patch('catastro.management.commands.catastro_migration_worker.migration_runner.job',
           return_value={'status': 'error', 'batch_size': 20,
                         'message': 'El archivo supera el límite de lectura.'})
    @patch('catastro.management.commands.catastro_migration_worker.Gateway')
    def test_watchdog_retries_the_observed_legacy_size_error(self, gateway, job, claim, run):
        from .management.commands.catastro_migration_worker import Command

        self.assertTrue(Command._recover_once('040126'))
        claim.assert_called_once()
        run.assert_called_once_with(
            '040126', 'azure-migration-watchdog', 5, 'recovered')
