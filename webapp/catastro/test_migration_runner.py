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

    def test_only_the_owner_job_can_continue(self):
        gateway = FakeGateway({'id': 'owner', 'status': 'running',
                               'expires_at': int(time.time()) + 120})
        self.assertTrue(migration_runner._owns(gateway, '040126', 'owner'))
        self.assertFalse(migration_runner._owns(gateway, '040126', 'other'))
