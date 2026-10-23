import json

from django.test import SimpleTestCase

from .geollaqta_bulk import backfill, lot_ids, migrate_pending, migration_status
from .master_store import MasterStore


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
