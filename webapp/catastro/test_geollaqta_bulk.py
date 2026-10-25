import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .geollaqta_bulk import (
    _activate_payload,
    backfill,
    lot_ids,
    migrate_pending,
    migration_status,
)
from .master_store import MasterStore
from .master_store import Conflict
from .storage import R2


class FakeCloud:
    def __init__(self, values):
        self.values = values

    def list_prefixes(self, prefix):
        return {'prefixes': [prefix + lot + '/' for lot in sorted(self.values)],
                'truncated': False}

    def get(self, key):
        return self.values[key.split('/')[2]], {}


class FakeRemote:
    def __init__(self):
        self.current = 10
        self.calls = []

    def revision(self):
        return self.current

    def read(self, sql, params=()):
        return []

    def call(self, payload):
        self.calls.append(payload)
        self.current += 1
        return {'result': {**payload['result'], 'revision': self.current}}


def manifest(lot_id):
    return {
        'lot_id': lot_id,
        'district_ubigeo': '040126',
        'extraction_revision': 2,
        'retrieved_at': '2026-10-22T12:00:00Z',
        'feature': {
            'attributes': {'ID_LOTE': lot_id, 'ID_DIST': '040126',
                           'COD_SECT': '04', 'COD_MZNA': '010', 'COD_LOTE': lot_id[-3:],
                           'NIVELES': 2, 'AREA_TER': 100, 'AREA_CON': 80},
            'geometry': {'rings': [[[-71.55, -16.36], [-71.549, -16.36],
                                    [-71.549, -16.359], [-71.55, -16.359],
                                    [-71.55, -16.36]]]},
        },
        'reports': [], 'artifacts': [], 'missing': [],
    }


class GeollaqtaBulkTests(SimpleTestCase):
    def setUp(self):
        ids = ['04012601001001', '04012601001002']
        self.cloud = FakeCloud({value: json.dumps(manifest(value)).encode() for value in ids})
        self.store = MasterStore()
        self.addCleanup(self.store.db.close)

    def test_existing_manifests_are_activated_in_master_without_download(self):
        ids, truncated = lot_ids('040126', self.cloud)
        self.assertEqual(ids, ['04012601001001', '04012601001002'])
        self.assertFalse(truncated)
        result = backfill(self.store, '040126', batch_size=20,
                          cloud=self.cloud, activate=True)
        self.assertEqual(result['available_lots'], 2)
        self.assertEqual(result['selected_lots'], 2)
        self.assertEqual(len(self.store.records({'ubigeo': '040126'})), 2)
        self.assertEqual(len(self.store.collection('040126', 'lote')['features']), 2)
        self.assertTrue(all(source['role'] == 'contributing' for source in self.store.summary()['sources']))

    def test_validated_revision_two_is_linked_in_bounded_d1_commits(self):
        remote = FakeRemote()
        status = migration_status(remote, '040126', self.cloud)
        self.assertEqual((status['source_lots'], status['linked_lots'],
                          status['pending_lots']), (2, 0, 2))
        result = migrate_pending(remote, '040126', 20, cloud=self.cloud)
        self.assertEqual((result['processed_lots'], result['linked_lots'],
                          result['pending_lots']), (2, 2, 0))
        self.assertTrue(result['done'])
        self.assertEqual(len(remote.calls), 2)

    def test_manifest_transport_has_a_larger_bounded_read_limit(self):
        cloud = R2.__new__(R2)
        with patch.object(R2, 'request', return_value=(b'{}', {})) as request:
            cloud.get_manifest('geollaqta/040126/04012601011003/datos.json')
        request.assert_called_once_with(
            'GET',
            'geollaqta/040126/04012601011003/datos.json',
            read_limit=R2.MANIFEST_READ_LIMIT + 1,
        )

    def test_unit_activation_is_split_into_bounded_source_feature_chunks(self):
        class Store:
            revision = 1
            plans = []

            def stage(self, payload, revision, actor):
                return {'revision': 1}

            def preview(self, plan):
                self.plans.append(plan)
                return {'token': 'token'}

            def apply(self, plan, token, actor):
                return {'revision': len(self.plans) + 1}

        store = Store()
        payload = {
            'version': {'id': 'batch'},
            'features': [{'id': 'lot', 'kind': 'lote'}]
                        + [{'id': f'unit-{index}', 'kind': 'unidad'}
                           for index in range(85)],
        }
        result = _activate_payload(store, payload, '040126', 'tester')
        unit_scopes = [
            plan['scope']['source_feature_ids']
            for plan in store.plans if plan['scope']['kind'] == 'unidad'
        ]
        self.assertEqual([len(values) for values in unit_scopes], [40, 40, 5])
        self.assertEqual(len(result['applied']), 4)

    def test_migration_retries_when_another_writer_changes_the_master(self):
        remote = FakeRemote()
        with patch('catastro.geollaqta_bulk.ScopeCommitGateway'), \
             patch('catastro.geollaqta_bulk.D1Store') as store_class, \
             patch('catastro.geollaqta_bulk.stage_batch',
                   side_effect=[Conflict('revision changed'), {'revision': 11}]) as stage:
            store_class.return_value = SimpleNamespace(
                db=SimpleNamespace(close=lambda: None), revision=10)
            result = migrate_pending(remote, '040126', 2, cloud=self.cloud)
        self.assertEqual(result['processed_lots'], 2)
        self.assertEqual(stage.call_count, 2)
