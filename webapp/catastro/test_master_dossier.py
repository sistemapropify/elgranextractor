import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve

from . import master_dossier, master_views


LOT = '04010206058015'
RECORD = '0401022012010025582'


class FakeCloud:
    def __init__(self):
        self.objects = {}

    def put(self, key, body):
        self.objects[key] = body

    def get_manifest(self, key):
        if key not in self.objects:
            from .storage import StorageError
            raise StorageError('R2 respondió HTTP 404.', 404)
        return self.objects[key], {}

    def get(self, key, max_bytes=None):
        body, headers = self.get_manifest(key)
        return body, headers


def manifest(facade=b'\xff\xd8\xff\xe0facade'):
    owner_fields = []
    for label, value in (
            ('NOMBRES Y APELLIDOS O RAZON SOCIAL', 'Titular Maestro'),
            ('TIPO DOCUMENTO', 'DNI'),
            ('NRO DOCUMENTO', '87654321'),
            ('(%)', '100'),
            ('CONDICION DEL TITULAR', 'PROPIETARIO')):
        owner_fields.append({
            'original_label': label,
            'section': 'Titulares',
            'values': [{'text': value, 'row': 42, 'bbox': [1, 1]}],
        })
    pages = [{
        'number': 1,
        'named_fields': [
            {'original_label': 'AREA LOTE (M2)', 'value': '200'},
            {'original_label': 'AREA CONSTRUIDA (M2)', 'value': '20.5'},
            {'original_label': 'FRENTE', 'label': 'Medida perimétrica · FRENTE',
             'value': '10'},
            {'original_label': 'FONDO', 'label': 'Medida perimétrica · FONDO',
             'value': '8'},
            *owner_fields,
        ],
        'numbered_fields': [],
        'additional_fields': [],
    }]
    report = b'%PDF-master'
    return {
        'schema_version': 1,
        'lot_id': LOT,
        'district_ubigeo': LOT[:6],
        'extraction_revision': 2,
        'retrieved_at': '2026-10-27T00:00:00+00:00',
        'feature': {
            'attributes': {
                'ID_LOTE': LOT,
                'ID_DIST': LOT[:6],
                'COD_SECT': '06',
                'COD_MZNA': '058',
                'COD_LOTE': '015',
                'AREA_TER': '210',
                'AREA_CON': '21',
            },
            'geometry': {'rings': []},
        },
        'artifacts': [
            {'type': 'facade_image', 'filename': 'facade.jpg',
             'sha256': hashlib.sha256(facade).hexdigest()},
            {'type': 'cadastral_report_pdf', 'filename': 'report.pdf',
             'record_id': RECORD,
             'sha256': hashlib.sha256(report).hexdigest()},
        ],
        'reports': [
            {'type': 'cadastral_report_pdf', 'record_id': RECORD,
             'form_number': '1/1', 'filename': 'report.pdf', 'pages': pages},
        ],
        'missing': ['Partida registral no publicada'],
        '_report_body': report,
    }


def archive_cloud():
    cloud = FakeCloud()
    value = manifest()
    report_body = value.pop('_report_body')
    cloud.put('geollaqta/' + LOT[:6] + '/' + LOT + '/datos.json',
              json.dumps(value, ensure_ascii=False).encode())
    cloud.put('geollaqta/' + LOT[:6] + '/' + LOT + '/facade.jpg',
              b'\xff\xd8\xff\xe0facade')
    cloud.put('geollaqta/' + LOT[:6] + '/' + LOT + '/report.pdf',
              report_body)
    return cloud


class MasterDossierTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_archived_lot_is_published_as_independent_master_layers(self):
        cloud = archive_cloud()
        with patch.object(master_dossier, '_from_d1', return_value=None):
            value = master_dossier.load(LOT, cloud=cloud)

        self.assertEqual(value['master_status'], 'archived_pending_d1')
        self.assertEqual(value['attributes']['gis_land_area'], 210.0)
        self.assertEqual(value['unit_attributes'][0]['land_area'], 200.0)
        self.assertEqual(value['unit_attributes'][0]['built_area'], 20.5)
        self.assertEqual(value['owners'][0]['name'], 'Titular Maestro')
        self.assertEqual(value['owners'][0]['document_number'], '87654321')
        self.assertEqual(value['gallery'][0]['url'],
                         '/catastro/api/maestro/lotes/' + LOT +
                         '/archivos/facade.jpg/')
        self.assertIn('report.pdf', {
            item['filename'] for item in value['media']})

        summary = master_dossier.summary(value)
        self.assertEqual(summary['metrics']['land_area'], 200.0)
        self.assertEqual(summary['metrics']['boundaries']['frente'], 10.0)
        self.assertTrue(summary['facade_url'].endswith('/archivos/facade.jpg/'))
        self.assertEqual(summary['source_label'],
                         'Catastro Maestro · archivo pendiente de normalización D1')

    def test_normalized_d1_record_uses_one_canonical_url_contract(self):
        entity_id = '11111111-2222-4333-8444-555555555555'
        model = SimpleNamespace(
            lot_identity=lambda lot: {
                'entity_id': entity_id,
                'version_id': 'v1',
                'source_id': 'geollaqta-040102',
                'version_label': 'tanda',
            },
            entity=lambda value: {
                'attributes': {'land_area': 200, 'block': '058'},
                'owners': [{'name': 'Titular D1'}],
                'unit_attributes': [],
                'media': [
                    {'id': 'facade-1', 'kind': 'facade_image',
                     'object_key': 'geollaqta/facade.jpg',
                     'details': {'source_record_id': RECORD}},
                    {'id': 'report-1', 'kind': 'cadastral_report_pdf',
                     'object_key': 'geollaqta/report.pdf',
                     'details': {'source_record_id': RECORD}},
                ],
                'identity_links': [], 'relationships': [], 'provenance': {},
                'boundary_segments': [], 'registral_acts': [], 'catalog': {},
            })
        with patch.object(master_dossier, 'D1ReadModel', return_value=model):
            value = master_dossier.load(LOT, surface='acm')

        self.assertEqual(value['master_status'], 'normalized_d1')
        self.assertEqual(value['owners'][0]['name'], 'Titular D1')
        self.assertEqual(value['gallery'][0]['url'],
                         '/acm/catastro/medios/facade-1/')
        self.assertEqual(value['master']['entity_id'], entity_id)

    def test_d1_changes_are_visible_on_the_next_consumer_request(self):
        calls = []
        class Model:
            def lot_identity(self, lot):
                return {'entity_id': '11111111-2222-4333-8444-555555555555',
                        'version_id': 'v1', 'source_id': 'geollaqta-040102'}
            def entity(self, entity_id):
                calls.append(entity_id)
                return {
                    'attributes': {'land_area': 100 + len(calls)},
                    'owners': [], 'unit_attributes': [], 'media': [],
                    'identity_links': [], 'relationships': [], 'provenance': {},
                    'boundary_segments': [], 'registral_acts': [], 'catalog': {},
                }
        with patch.object(master_dossier, 'D1ReadModel', return_value=Model()):
            first = master_dossier.load(LOT)
            second = master_dossier.load(LOT)
        self.assertEqual(first['attributes']['land_area'], 101)
        self.assertEqual(second['attributes']['land_area'], 102)
        self.assertEqual(len(calls), 2)

    def test_archive_asset_is_whitelisted_and_integrity_checked(self):
        cloud = archive_cloud()
        body, content_type = master_dossier.archive_asset(
            LOT, 'facade.jpg', cloud=cloud)
        self.assertEqual(body, b'\xff\xd8\xff\xe0facade')
        self.assertEqual(content_type, 'image/jpeg')
        with self.assertRaises(ValueError):
            master_dossier.archive_asset(LOT, '../datos.json', cloud=cloud)
        with self.assertRaises(ValueError):
            master_dossier.archive_asset(LOT, 'not-listed.jpg', cloud=cloud)

    def test_canonical_routes_resolve_the_lot_and_archive_filename(self):
        dossier_match = resolve('/catastro/api/maestro/lotes/' + LOT + '/ficha/')
        asset_match = resolve(
            '/catastro/api/maestro/lotes/' + LOT + '/archivos/facade.jpg/')
        self.assertEqual(dossier_match.kwargs, {'lot_id': LOT})
        self.assertEqual(asset_match.kwargs,
                         {'lot_id': LOT, 'filename': 'facade.jpg'})
        request = RequestFactory().get(
            '/catastro/api/maestro/lotes/' + LOT + '/ficha/')
        request.current_user = SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=True,
            is_superuser=True)
        expected = {'lot_id': LOT, 'master_status': 'archived_pending_d1'}
        with patch.object(master_dossier, 'load', return_value=expected) as load:
            response = master_views.lot_dossier(request, LOT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), expected)
        load.assert_called_once_with(LOT, None, surface='master')
