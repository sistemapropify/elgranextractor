import unittest
from unittest.mock import patch

from django.test import SimpleTestCase

from . import cofopri_vector_migration
from .master_store import MasterStore


def _feature(object_id, rpu, block='A', lot='1'):
    return {
        'type': 'Feature',
        'id': object_id,
        'geometry': {'type': 'Polygon', 'coordinates': [[
            [-71.48, -16.47], [-71.4799, -16.47],
            [-71.4799, -16.4699], [-71.48, -16.47],
        ]]},
        'properties': {
            'OBJECTID': object_id,
            'ID_PREDIO_RPU': rpu,
            'COD_MZNA': block,
            'COD_LOTE': lot,
            'AREA_TER': 100.0,
            'TIPO_USO': 'VIVIENDA',
        },
    }


class CofopriVectorMigrationTests(SimpleTestCase):
    def test_wgs84_and_psad56_are_merged_by_rpu_before_staging(self):
        snapshots = {
            'psad56': [_feature(1, 'P06121499')],
            'wgs84': [
                {
                    **_feature(2, 'P06121499'),
                    'properties': {
                        'OBJECTID': 2, 'ID_PREDIO_RPU': 'P06121499',
                        'COD_MZNA': 'A', 'COD_LOTE': '1',
                    },
                },
                _feature(3, 'P06121500', lot='2'),
            ],
        }
        with patch(
                'catastro.cofopri_vector_migration.vector_snapshots.read_snapshot',
                side_effect=lambda ubigeo, layer, cloud=None, source=None:
                    {'features': snapshots[source]}):
            lots = cofopri_vector_migration.merged_formalization_lots(
                '040105', cloud=object())
        self.assertEqual([item['id'] for item in lots],
                         ['P06121499', 'P06121500'])
        payload = cofopri_vector_migration.batch_payload(
            '040105', 'Characato', lots, 1)
        self.assertEqual(len(payload['features']), 2)
        self.assertEqual(
            payload['features'][0]['fields']['land_area'], 100.0)
        self.assertEqual(
            payload['identifiers'][0]['scheme'], 'COFOPRI_RPU')

    def test_vector_batch_stages_and_activates_through_master_store(self):
        lots = [
            {'id': 'P06121499', 'source': 'psad56',
             'properties': _feature(1, 'P06121499')['properties'],
             'geometry': _feature(1, 'P06121499')['geometry']},
        ]
        payload = cofopri_vector_migration.batch_payload(
            '040105', 'Characato', lots, 1)
        store = MasterStore()
        self.addCleanup(store.db.close)
        staged = store.stage(payload, store.revision, 'test')
        plan = {
            'revision': store.revision,
            'version_id': staged['version_id'],
            'mode': 'fill',
            'scope': {'ubigeo': '040105', 'kind': 'lote'},
            'fields': [],
            'reason': 'Migración vectorial de prueba',
        }
        preview = store.preview(plan)
        store.apply(plan, preview['token'], 'test')
        records = store.records({'ubigeo': '040105'})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['lot'], '1')
        self.assertEqual(records[0]['land_area'], 100.0)
