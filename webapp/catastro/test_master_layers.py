import json
import os
from django.core.cache import cache
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve
from . import manual_parks, master_layers, master_views, vector_snapshots
from .storage import StorageError


class FakeSnapshotCloud:
    def __init__(self):
        self.objects = {}

    def put_verified(self, key, body, content_type):
        self.objects[key] = body

    def get_manifest(self, key):
        if key not in self.objects:
            raise StorageError('R2 respondió HTTP 404.', 404)
        return self.objects[key], {}


class MasterGeometryTests(SimpleTestCase):
    def request(self, path, staff=True):
        request = RequestFactory().get(path)
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True,
                                               is_staff=staff, is_superuser=False)
        return request

    def test_cayma_complements_geo_without_changing_its_published_inventory(self):
        data = master_layers.catalogue()
        cayma = next(d for d in data['districts'] if d['ubigeo'] == '040103')
        self.assertEqual(cayma['published_lots'], 0)
        self.assertEqual(cayma['sources'], ['cayma-pud-2006-eu03', 'cayma-sector-32-provisional'])
        source = next(s for s in data['sources'] if s['id'] == cayma['sources'][0])
        self.assertTrue(source['reference_only'])
        self.assertFalse(source['default_visible'])
        self.assertFalse(source['contributes'])
        self.assertEqual(source['role'],'backup')
        self.assertFalse(source['georeferencing']['datum_documented'])
        self.assertFalse(source['qa']['complete_inventory'])
        self.assertEqual(source['crs'], 'EPSG:4326')

    def test_catalogue_remains_available_when_snapshot_storage_is_unconfigured(self):
        with patch('catastro.vector_snapshots.catalog_sources',
                   side_effect=StorageError('Configura las credenciales privadas de R2.')):
            data = master_layers.catalogue()
        self.assertTrue(data['districts'])
        self.assertTrue(any(source['id'] == 'geollaqta' for source in data['sources']))

    def test_d1_catalogue_uses_bounded_reads_without_loading_the_authoring_store(self):
        summaries = {'040126': {'ubigeo': '040126', 'revision': 4114,
                                'lotes': 5240, 'manzanas': 0}}
        snapshots = [{
            'id': 'vectores-040126', 'name': 'vectores', 'ubigeo': '040126',
            'districts': ['040126'], 'active': True, 'default_visible': True,
            'contributes': False, 'reference_only': False, 'role': 'snapshot',
            'transport': 'snapshot', 'crs': 'EPSG:4326',
            'layers': {'lotes': {'count': 5240, 'kind': 'polygon'},
                       'manzanas': {'count': 319, 'kind': 'polygon'}},
        }]
        with patch.dict(os.environ, {'CATASTRO_MASTER_STORAGE': 'd1',
                                     'CATASTRO_MASTER_ENABLED': '1'}), \
                patch('catastro.source_manager.district_summaries',
                      return_value=summaries), \
                patch('catastro.vector_snapshots.catalog_sources',
                      return_value=snapshots), \
                patch('catastro.source_manager.store',
                      side_effect=AssertionError('No debe cargar D1Store')):
            data = master_layers.catalogue()

        source = next(item for item in data['sources'] if item['id'] == 'borrador-040126')
        self.assertEqual(source['revision'], 4114)
        self.assertEqual(source['layers']['lotes']['count'], 5240)
        self.assertFalse(source['reference_only'])
        yanahuara = next(item for item in data['districts'] if item['ubigeo'] == '040126')
        self.assertIn('borrador-040126', yanahuara['sources'])
        self.assertIn('vectores-040126', yanahuara['sources'])
        snapshot = next(item for item in data['sources'] if item['id'] == 'vectores-040126')
        self.assertNotIn('lotes', snapshot['layers'])
        self.assertEqual(snapshot['layers']['manzanas']['count'], 319)

    def test_vector_snapshot_chunks_are_reassembled_independently(self):
        cache.clear()
        cloud = FakeSnapshotCloud()
        collection = {
            'type': 'FeatureCollection', 'ubigeo': '040102', 'layer': 'lotes',
            'features': [{'type': 'Feature', 'id': index,
                          'properties': {'COD_LOTE': str(index)},
                          'geometry': {'type': 'Polygon', 'coordinates': []}}
                         for index in range(9001)],
        }
        row = vector_snapshots.save_snapshot(
            '040102', 'lotes', collection, cloud=cloud,
            captured_at='2026-10-27T00:00:00+00:00')
        self.assertEqual(row['features'], 9001)
        self.assertEqual(len(row['chunks']), 3)
        restored = vector_snapshots.read_snapshot('040102', 'lotes', cloud=cloud)
        self.assertEqual(restored['total_features'], 9001)
        manifest = vector_snapshots.snapshot_manifest('040102', 'lotes', cloud=cloud)
        self.assertEqual(manifest['parts'], 3)
        self.assertEqual(manifest['features'], 9001)
        self.assertEqual(
            len(vector_snapshots.read_snapshot_part('040102', 'lotes', 1, cloud=cloud)['features']),
            4000)
        self.assertIn('geollaqta/vectores/index.json', cloud.objects)

    def test_vector_manifest_url_passes_the_layer_parameter_to_the_view(self):
        request = RequestFactory().get(
            '/catastro/api/maestro/vectores/040102/manzanas/manifiesto/')
        request.current_user = SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=True, is_superuser=True)
        match = resolve(request.path)
        self.assertEqual(match.kwargs, {'ubigeo': '040102', 'layer_key': 'manzanas'})
        with patch('catastro.vector_snapshots.snapshot_manifest',
                   return_value={'ubigeo': '040102', 'layer': 'manzanas',
                                 'parts': 1, 'features': 1}):
            response = match.func(request, **match.kwargs)
        self.assertEqual(response.status_code, 200)

    def test_manual_park_lots_are_saved_independently_by_district(self):
        cloud = FakeSnapshotCloud()
        initial = manual_parks.read('040102', cloud=cloud)
        lot_id = '04010201001001'
        saved = manual_parks.save(
            '040102', [lot_id], initial['token'], 'editor', cloud=cloud)
        self.assertEqual(saved['lots'], [lot_id])
        self.assertEqual(saved['updated_by'], 'editor')
        with self.assertRaises(manual_parks.Conflict):
            manual_parks.save('040102', [], initial['token'], 'editor', cloud=cloud)
        with self.assertRaises(ValueError):
            manual_parks.save(
                '040102', ['04012601001001'], saved['token'], 'editor', cloud=cloud)

    def test_manual_corner_and_park_front_layers_have_independent_colors(self):
        cloud = FakeSnapshotCloud()
        initial = manual_parks.read('040102', cloud=cloud)
        corner = '04010201001001'
        face_park = '04010201001002'
        saved = manual_parks.save_classifications(
            '040102',
            {
                'parks': ['04010201001003'],
                'corners': [corner],
                'faces_park': [face_park],
                'colors': {'parks': '#112233', 'corners': '#445566',
                           'faces_park': '#778899'},
            },
            initial['token'], 'editor', cloud=cloud,
        )
        self.assertEqual(saved['corners'], [corner])
        self.assertEqual(saved['faces_park'], [face_park])
        self.assertEqual(saved['colors']['corners'], '#445566')
        self.assertEqual(saved['colors']['faces_park'], '#778899')
        restored = manual_parks.read('040102', cloud=cloud)
        self.assertEqual(restored['token'], saved['token'])
        self.assertEqual(restored['parks'], ['04010201001003'])

    def test_classification_api_saves_all_layers_and_colors(self):
        match = resolve('/catastro/api/maestro/clasificaciones/')
        request = RequestFactory().post(
            match.route,
            data=json.dumps({
                'ubigeo': '040102', 'parks': [],
                'corners': ['04010201001001'],
                'faces_park': ['04010201001002'],
                'colors': {'corners': '#123456', 'faces_park': '#abcdef',
                           'parks': '#654321'},
                'token': 'old',
            }),
            content_type='application/json',
        )
        request.current_user = SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=True,
            is_superuser=True, username='editor')
        request._dont_enforce_csrf_checks = True
        expected = {'ubigeo': '040102', 'corners': ['04010201001001'],
                    'faces_park': ['04010201001002'], 'parks': []}
        with patch('catastro.master_views.manual_parks.save_classifications',
                   return_value=expected) as save:
            response = match.func(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['corners'], expected['corners'])
        save.assert_called_once()

    def test_draft_layer_keeps_master_identity_and_is_not_reference_geometry(self):
        summary = {'ubigeo': '040126', 'revision': 4114,
                   'lotes': 1, 'manzanas': 0}
        feature = {
            'type': 'Feature', 'id': 'entity-1',
            'geometry': {'type': 'Polygon', 'coordinates': [
                [[-71.55, -16.36], [-71.549, -16.36], [-71.549, -16.359],
                 [-71.55, -16.359], [-71.55, -16.36]]]},
            'properties': {'ubigeo': '040126', 'sector': '01', 'block': '004',
                           'lot': '010', 'source_feature_id': '04012601004010'},
            'provenance': {'$geometry': {'version_id': 'version-1'}},
        }
        with patch.dict(os.environ, {'CATASTRO_MASTER_STORAGE': 'd1',
                                     'CATASTRO_MASTER_ENABLED': '1'}), \
                patch('catastro.source_manager.district_summary',
                      return_value=summary), \
                patch('catastro.source_manager.collection',
                      return_value={'type': 'FeatureCollection',
                                    'features': [feature], 'revision': 4114}), \
                patch('catastro.source_manager.store',
                      side_effect=AssertionError('No debe cargar D1Store')):
            data = master_layers.layer('borrador-040126', 'lotes', '040126')

        properties = data['features'][0]['properties']
        self.assertEqual(properties['ID_LOTE'], '04012601004010')
        self.assertEqual(properties['COD_SECT'], '01')
        self.assertEqual(properties['COD_MZNA'], '004')
        self.assertEqual(properties['COD_LOTE'], '010')
        self.assertEqual(properties['ELEMENT_ID'], 'entity-1')
        self.assertFalse(properties['REFERENCE_ONLY'])
        self.assertFalse(data['reference_only'])
        published = master_layers.public_draft_layer(data)
        self.assertEqual(published['features'][0]['properties']['ID_LOTE'],
                         '04012601004010')

    def test_sector32_priority_clips_the_2006_backup_without_overlap(self):
        from shapely.geometry import shape
        old = master_layers.layer('cayma-pud-2006-eu03', 'lotes', '040103')
        sector = master_layers.layer('cayma-sector-32-provisional', 'lotes', '040103')
        modified = max(
            (master_layers.SOURCES[master_layers.SECTOR32] / name).stat().st_mtime_ns
            for name in ('lotes.geojson', 'manzanas.geojson'))
        mask = master_layers._sector32_mask(modified)
        self.assertEqual(len(sector['features']), 438)
        self.assertLess(len(old['features']), 22405)
        self.assertTrue(all(shape(feature['geometry']).intersection(mask).area < 1e-14
                            for feature in old['features']))

    def test_reference_ids_are_unique_and_never_become_cadastral_codes(self):
        source = 'cayma-pud-2006-eu03'
        lots = master_layers.layer(source, 'lotes', '040103')['features']
        blocks = master_layers.layer(source, 'manzanas', '040103')['features']
        block_ids = {b['id'] for b in blocks}
        self.assertEqual(len(block_ids), len(blocks))
        self.assertEqual(len({f['id'] for f in lots}), len(lots))
        self.assertFalse(block_ids.intersection(f['id'] for f in lots))
        for f in lots:
            self.assertTrue(f['id'].startswith(source+':lote:'))
            self.assertIsNone(f['properties']['ID_LOTE'])
            self.assertIsNone(f['properties']['COD_LOTE'])
            self.assertIsNone(f['properties']['COD_MZNA'])
            self.assertIsNone(f['properties']['ANIO_CAT'])
            self.assertIn(f['properties']['BLOCK_REF'], block_ids)
            self.assertEqual(f['properties']['ID_DIST'], '040103')
            polygons = ([f['geometry']['coordinates']]
                        if f['geometry']['type'] == 'Polygon'
                        else f['geometry']['coordinates'])
            for rings in polygons:
                for ring in rings:
                    self.assertEqual(ring[0], ring[-1])
                    self.assertGreaterEqual(len(ring), 4)
                    self.assertTrue(all(-71.6 < p[0] < -71.5 and -16.4 < p[1] < -16.29
                                        for p in ring))

    def test_reference_revisions_match_the_shared_acm_provider_snapshot(self):
        from . import master
        revisions = master_layers.revisions()
        providers = {item['id']: item['placement']['revision']
                     for item in master.configuration()['providers']
                     if item.get('transport') == 'master'
                     and 'revision' in item.get('placement', {})}
        self.assertEqual(revisions['cayma-pud-2006-eu03'],
                         providers['cayma-pud-2006-eu03'])
        self.assertEqual(revisions['cayma-sector-32-provisional'],
                         providers['cayma-sector-32-provisional'])

    def test_acm_configuration_has_no_primary_cadastral_provider(self):
        from . import master
        config = master.configuration()
        self.assertFalse(any(item.get('id') == 'geollaqta'
                             for item in config['providers']))
        snapshot = next(item for item in config['providers']
                        if item.get('id') == 'vectores-040126')
        self.assertEqual(snapshot['role'], 'snapshot')
        self.assertEqual(snapshot['transport'], 'master')
        self.assertEqual(snapshot['geometry_url'],
                         '/acm/catastro/fuentes/vectores-040126/radio/')
        self.assertEqual(snapshot['bbox'],
                         [-71.57235497, -16.41116467,
                          -71.53480113, -16.3797898])

    def test_snapshot_radius_is_the_shared_acm_geometry_contract(self):
        source = {
            'id': 'vectores-040126', 'name': 'Catastro Maestro · Yanahuara',
            'active': True, 'layers': {'lotes': {'count': 1},
                                      'manzanas': {'count': 0}},
        }
        collection = {
            'features': [{
                'type': 'Feature', 'id': 7,
                'properties': {'ID_LOTE': '04012603016005',
                               'COD_SECT': '03', 'COD_MZNA': '016',
                               'COD_LOTE': '005'},
                'geometry': {'type': 'Polygon', 'coordinates': [[
                    [-71.55, -16.36], [-71.549, -16.36],
                    [-71.549, -16.359], [-71.55, -16.359],
                    [-71.55, -16.36]]]},
            }],
        }
        with patch('catastro.vector_snapshots.catalog_sources',
                   return_value=[source]), \
                patch('catastro.vector_snapshots.read_snapshot',
                      return_value=collection):
            value = master_layers.radius(
                'vectores-040126', '-16.36', '-71.55', '500')
        self.assertEqual(value['source_id'], 'vectores-040126')
        self.assertEqual(value['lots']['total'], 1)
        feature = value['lots']['features'][0]
        self.assertEqual(feature['id'], 'vectores-040126:lote:7')
        self.assertEqual(feature['properties']['SOURCE_ID'],
                         'vectores-040126')

    def test_invalid_source_district_and_bbox_are_rejected(self):
        for args in [('../secret', 'lotes', '040103'), ('cayma-pud-2006-eu03', '../metadata', '040103'),
                     ('cayma-pud-2006-eu03', 'lotes', '040126')]:
            with self.assertRaises(ValueError):
                master_layers.layer(*args)
        for bounds in ['NaN,0,1,1', '0,0,1', '2,0,1,2', '-181,0,1,2']:
            with self.assertRaises(ValueError):
                master_layers.bbox(bounds)

    def test_bbox_preserves_whole_geometry_and_disjoint_area_is_empty(self):
        source = 'cayma-pud-2006-eu03'
        original = master_layers.layer(source, 'lotes', '040103')
        first = original['features'][0]
        p = first['geometry']['coordinates'][0][0]
        small = master_layers.layer(source, 'lotes', '040103', [p[0]-1e-7,p[1]-1e-7,p[0]+1e-7,p[1]+1e-7])
        self.assertIn(first, small['features'])
        self.assertEqual(master_layers.layer(source, 'lotes', '040103', [-74,-15,-73,-14])['features'], [])

    def test_access_control_precedes_geometry_read(self):
        anonymous = RequestFactory().get('/catastro/api/maestro/catalogo/')
        with patch('catastro.master_layers.catalogue') as read:
            self.assertEqual(master_views.catalogue(anonymous).status_code, 401)
            self.assertEqual(master_views.catalogue(self.request(anonymous.path, staff=False)).status_code, 403)
            read.assert_not_called()
        response = master_views.layer(self.request('/catastro/api/maestro/fuentes/cayma-pud-2006-eu03/lotes/?ubigeo=040103'),
                                      'cayma-pud-2006-eu03', 'lotes')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['reference_only'])

    @override_settings(GOOGLE_MAPS_API_KEY='test-key')
    def test_master_page_exposes_two_common_layers_without_a_collector(self):
        with patch('django.template.base.Template._render', lambda template, context: template.nodelist.render(context)):
            response = master_views.viewer(self.request('/catastro/maestro/'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="master-manzanas"', html)
        self.assertIn('id="master-lotes"', html)
        self.assertIn('id="master-detail-card"', html)
        self.assertIn('id="master-detail-close"', html)
        self.assertIn('id="master-classification-kind"', html)
        self.assertIn('id="master-color-corners"', html)
        self.assertIn('id="master-color-faces-park"', html)
        self.assertIn('id="master-layer-corners"', html)
        self.assertNotIn('id="master-cayma-preview"', html)
        self.assertNotIn('Ver Cayma temporal', html)
        self.assertNotIn('geollaqta-data.js', html)
        self.assertNotIn('geollaqta-district.js', html)
        self.assertNotIn('collection-form', html)
        self.assertIn('catastro-maestro.js?v=31', html)
