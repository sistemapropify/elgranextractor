import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings
from . import master_layers, master_views


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
        self.assertEqual(cayma['sources'], ['cayma-pud-2006-eu03'])
        source = next(s for s in data['sources'] if s['id'] == cayma['sources'][0])
        self.assertTrue(source['reference_only'])
        self.assertFalse(source['georeferencing']['datum_documented'])
        self.assertFalse(source['qa']['complete_inventory'])
        self.assertEqual(source['crs'], 'EPSG:4326')

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
            for ring in f['geometry']['coordinates']:
                self.assertEqual(ring[0], ring[-1])
                self.assertGreaterEqual(len(ring), 4)
                self.assertTrue(all(-71.6 < p[0] < -71.5 and -16.4 < p[1] < -16.29 for p in ring))

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
        self.assertNotIn('collection-form', html)
        self.assertIn('catastro-maestro.js', html)
