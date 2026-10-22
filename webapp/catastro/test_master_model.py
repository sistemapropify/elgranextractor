import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from . import master_model
from .master_store import MasterStore


class MasterModelTests(SimpleTestCase):
    def test_every_exposed_table_exists_in_the_authoritative_schema(self):
        schema_path = (Path(__file__).resolve().parents[2] / 'cloudflare'
                       / 'catastro-maestro' / 'schema.sql')
        schema = schema_path.read_text(encoding='utf8')
        names = set(re.findall(r'CREATE TABLE\s+([a-z_]+)', schema))
        exposed = {
            table['name']
            for group in master_model.value()['groups']
            for table in group['tables']
        }
        self.assertTrue(exposed)
        self.assertEqual(exposed - names, set())

    def test_canonical_query_joins_plan_code_to_stable_entity_and_active_geometry(self):
        store = MasterStore()
        self.addCleanup(store.db.close)
        payload = {
            'source': {'id': 'geollaqta-test', 'name': 'Geollaqta prueba', 'ubigeo': '040126'},
            'version': {
                'id': 'geollaqta-test-v1',
                'label': 'Prueba',
                'crs': 'EPSG:4326',
                'georeferencing': {
                    'status': 'verified',
                    'method': 'EPSG:4326',
                    'evidence': {'service': 'fixture'},
                },
            },
            'features': [{
                'id': '04012601001001',
                'kind': 'lote',
                'fields': {
                    'ubigeo': '040126',
                    'sector': '01',
                    'block': '001',
                    'lot': '001',
                    'land_area': 120,
                    'built_area': 80,
                    'floors': 2,
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [-71.55, -16.36], [-71.549, -16.36],
                        [-71.549, -16.359], [-71.55, -16.359],
                        [-71.55, -16.36],
                    ]],
                },
            }],
            'identifiers': [{
                'target_ref': 'lote:04012601001001',
                'scheme': 'cofopri-lote',
                'value': '04012601001001',
                'status': 'verified',
            }],
        }
        store.stage(payload, store.revision, 'test-admin')
        plan = {
            'revision': store.revision,
            'version_id': 'geollaqta-test-v1',
            'mode': 'fill',
            'scope': {'ubigeo': '040126', 'kind': 'lote'},
            'fields': [],
            'reason': 'Prueba del modelo SQL',
        }
        preview = store.preview(plan)
        store.apply(plan, preview['token'], 'test-admin')

        row = store.db.execute(master_model.LOT_QUERY, ('04012601001001',)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['plan_lot_id'], '04012601001001')
        self.assertEqual(row['sector'], '01')
        self.assertEqual(row['block'], '001')
        self.assertEqual(row['lot'], '001')
        self.assertEqual(row['geometry_source_id'], 'geollaqta-test')
        self.assertEqual(json.loads(row['geometry_json'])['type'], 'Polygon')
        self.assertEqual(json.loads(row['identifiers_json'])[0]['scheme'], 'cofopri-lote')
