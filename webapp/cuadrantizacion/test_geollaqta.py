import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from . import geollaqta as geo


def polygon(x=0, y=0, size=1):
    return [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]


def feature(object_id=12343, district='040126'):
    return {'attributes': {'OBJECTID': object_id, 'ID_DIST': district,
                           'ID_LOTE': '04012607042018    ', 'ANIO_CAT': '2013',
                           'COD_LOTE': '018', 'AREA_TER': None, 'secret': 'ignored'},
            'geometry': {'rings': [polygon(-71.566, -16.407, .0001)]}}


class GeollaqtaTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def request(self, query=None, authenticated=True):
        request = self.factory.get('/', query or {})
        request.current_user = SimpleNamespace(is_active=True, is_authenticated=authenticated)
        return request

    def test_authentication_precedes_every_external_request(self):
        with patch.object(geo, '_query') as query:
            request = self.request(authenticated=False)
            self.assertEqual(geo.coverage(request).status_code, 401)
            self.assertEqual(geo.lots(request).status_code, 401)
            self.assertEqual(geo.detail(request, 12343).status_code, 401)
            query.assert_not_called()

    def test_non_get_methods_are_rejected(self):
        self.assertEqual(geo.coverage(self.factory.post('/')).status_code, 405)

    def test_invalid_or_excessive_viewports_never_reach_cofopri(self):
        with patch.object(geo, '_query') as query:
            for bbox in (None, '', 'nan,0,1,1', '0,0,1,1', '1,0,0,1', '0,0,1', '0,-100,.01,-99.99'):
                response = geo.lots(self.request({'bbox': bbox} if bbox is not None else {}))
                self.assertEqual(response.status_code, 400, bbox)
            query.assert_not_called()

    def test_explicit_id_batches_bound_the_load_and_report_truncation(self):
        calls = []
        def query(**params):
            calls.append(params)
            if params.get('returnIdsOnly'):
                return {'objectIds': list(range(1, 1002))}
            return {'features': [feature(int(oid)) for oid in params['objectIds'].split(',')]}
        with patch.object(geo, '_query', side_effect=query):
            data = json.loads(geo.lots(self.request({'bbox': '-71.57,-16.41,-71.56,-16.40'})).content)
        self.assertEqual(len(data['features']), 1000)
        self.assertEqual(data['total_in_view'], 1001)
        self.assertTrue(data['truncated'])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]['where'], "ID_DIST='040126'")
        self.assertEqual(calls[1]['outSR'], 4326)
        self.assertEqual(len(calls[1]['objectIds'].split(',')), 500)
        self.assertNotIn('secret', data['features'][0]['properties'])
        self.assertEqual(data['features'][0]['properties']['ID_LOTE'], '04012607042018')
        self.assertIsNone(data['features'][0]['properties']['AREA_TER'])

    def test_missing_coverage_is_distinct_from_upstream_failure(self):
        with patch.object(geo, '_query', return_value={'objectIds': None}):
            data = json.loads(geo.lots(self.request({'bbox': '-71.58,-16.41,-71.57,-16.40'})).content)
            self.assertEqual(data['features'], [])
            self.assertEqual(data['total_in_view'], 0)
        cache.clear()
        with patch.object(geo, '_query', side_effect=geo.UpstreamError('Unavailable')):
            self.assertEqual(geo.lots(self.request({'bbox': '-71.58,-16.41,-71.57,-16.40'})).status_code, 502)

    def test_invalid_geometries_are_reported_and_foreign_districts_filtered(self):
        invalid = feature(2)
        invalid['geometry']['rings'][0][0][0] = float('nan')
        with patch.object(geo, '_query', side_effect=[{'objectIds': [1, 2, 3]},
                {'features': [feature(1), invalid, feature(3, '040104')]}]):
            data = json.loads(geo.lots(self.request({'bbox': '-71.57,-16.41,-71.56,-16.40'})).content)
        self.assertEqual(len(data['features']), 1)
        self.assertEqual(data['skipped'], 1)

    def test_holes_disjoint_polygons_and_islands_are_preserved(self):
        outer, hole, island, separate = polygon(0, 0, 10), polygon(2, 2, 6), polygon(3, 3, 1), polygon(20, 20, 2)
        result = geo._geometry({'rings': [hole[::-1], separate, island, outer]})
        self.assertEqual(result['type'], 'MultiPolygon')
        self.assertEqual(result['coordinates'][0], [outer, hole[::-1]])
        self.assertEqual(len(result['coordinates']), 3)
        self.assertEqual(geo._geometry({'rings': [outer]})['type'], 'Polygon')

    def test_gallery_only_accepts_real_cofopri_photo_and_ficha_links(self):
        parser = geo.GalleryParser()
        good = 'https://catastro.cofopri.gob.pe/img_catastro/040126/07042018.jpg'
        ficha = geo.PORTAL + 'reportefichas/vistapdf/fichain.php?id=0401262013010431544'
        parser.feed(f'<img src="{good}"><img src="{good}"><a href="{ficha}">Ficha</a>'
                    '<img src="https://evil.test/a.jpg"><img src="/img_catastro/040104/a.jpg">'
                    '<img src="/geollaqta/img/logo.png"><a href="javascript:alert(1)">x</a>')
        self.assertEqual(parser.images, [good])
        self.assertEqual(parser.records, [ficha])

    def test_lot_detail_is_revalidated_for_yanahuara(self):
        with patch.object(geo, '_query', return_value={'features': []}) as query, patch.object(geo, '_gallery') as gallery:
            self.assertEqual(geo.detail(self.request(), 12343).status_code, 404)
            self.assertEqual(query.call_args.kwargs['where'], "OBJECTID=12343 AND ID_DIST='040126'")
            gallery.assert_not_called()

    def test_gallery_failure_keeps_the_lot_metadata_and_original_link(self):
        with patch.object(geo, '_query', return_value={'features': [feature()]}), \
                patch.object(geo, '_gallery', side_effect=geo.UpstreamError('Unavailable')):
            response = geo.detail(self.request(), 12343)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['gallery_status'], 'unavailable')
        self.assertEqual(data['images'], [])
        self.assertTrue(data['gallery_url'].endswith('id_lote=04012607042018'))

    def test_service_errors_are_never_cached_as_empty_success(self):
        response = b'{"error":{"code":400,"message":"Invalid query"}}'
        with patch.object(geo, '_download', return_value=response):
            self.assertEqual(geo.coverage(self.request()).status_code, 502)
        self.assertIsNone(cache.get('geollaqta-coverage-v3:040126'))

    def test_layer_allowlist_blocks_arbitrary_service_access(self):
        with patch.object(geo, '_query') as query:
            self.assertEqual(geo.layer(self.request(), 'https://evil.test').status_code, 404)
            query.assert_not_called()

    def test_roads_use_their_actual_district_field_and_line_geometry(self):
        road = {'attributes': {'OBJECTID': 1, 'ID_UBI_GEO': '040126', 'NOM_VIA': 'Ejemplo'},
                'geometry': {'paths': [[[-71.56, -16.4], [-71.56, -16.401]]]}}
        with patch.object(geo, '_query', side_effect=[{'objectIds': [1]}, {'features': [road]}]) as query:
            data = json.loads(geo.layer(self.request({'bbox': '-71.57,-16.41,-71.56,-16.40'}), 'ejes-vias').content)
        self.assertEqual(query.call_args_list[0].kwargs['where'], "ID_UBI_GEO='040126'")
        self.assertEqual(data['features'][0]['geometry']['type'], 'LineString')

    def test_entrances_preserve_point_coordinates(self):
        self.assertEqual(geo._esri_geometry({'x': -71.56, 'y': -16.4}, 'point'),
                         {'type': 'Point', 'coordinates': [-71.56, -16.4]})

    def test_azure_transport_authorizes_without_server_outbound_calls(self):
        with patch.dict(geo.os.environ, {'WEBSITE_SITE_NAME':'granextractorservice'}), patch.object(geo, '_query') as query:
            response=geo.coverage(self.request())
            data=json.loads(response.content)
            self.assertEqual(data['transport'],'browser')
            self.assertEqual(data['ubigeo'],'040126')
            self.assertEqual(data['layers']['lotes']['id'],10)
            query.assert_not_called()
            self.assertEqual(geo.coverage(self.request(authenticated=False)).status_code,401)

    def test_catalog_is_authenticated_and_does_not_query_upstream(self):
        with patch.object(geo, '_query') as query:
            self.assertEqual(geo.districts(self.request(authenticated=False)).status_code, 401)
            data = json.loads(geo.districts(self.request()).content)
            self.assertEqual(len(data['districts']), 29)
            self.assertEqual(data['districts_with_lots'], 10)
            self.assertEqual(data['default_district'], '040126')
            query.assert_not_called()

    def test_metadata_does_not_wait_for_the_external_count(self):
        with patch.object(geo, '_query') as query:
            data = json.loads(geo.coverage(self.request({'ubigeo': '040104', 'metadata': '1'})).content)
            self.assertEqual(data['transport'], 'server')
            self.assertEqual(data['layers']['lotes']['id'], 10)
            self.assertEqual(data['ubigeo'], '040104')
            query.assert_not_called()

    def test_district_allowlist_rejects_injection_before_query(self):
        with patch.object(geo, '_query') as query:
            for code in ["040126' OR 1=1", '0401', '150101', '040130']:
                request = self.request({'ubigeo': code, 'bbox': '-71.57,-16.41,-71.56,-16.40'})
                self.assertEqual(geo.coverage(request).status_code, 400)
                self.assertEqual(geo.lots(request).status_code, 400)
                self.assertEqual(geo.detail(request, 12343).status_code, 400)
            query.assert_not_called()

    def test_district_caches_are_isolated(self):
        with patch.object(geo, '_query', side_effect=[{'count': 5240}, {'count': 15636}]) as query:
            for code, expected in [('040126', 5240), ('040104', 15636), ('040126', 5240)]:
                data = json.loads(geo.coverage(self.request({'ubigeo': code})).content)
                self.assertEqual(data['total'], expected)
                self.assertEqual(data['ubigeo'], code)
            self.assertEqual(query.call_count, 2)
            self.assertEqual(query.call_args.kwargs['where'], "ID_DIST='040104'")

    def test_other_district_lot_and_gallery_are_scoped(self):
        item = feature(12290, '040104')
        item['attributes']['ID_LOTE'] = '04010484005007'
        with patch.object(geo, '_query', return_value={'features': [item]}) as query, \
                patch.object(geo, '_gallery', return_value={'images': [], 'records': [], 'gallery_status': 'available'}) as gallery:
            response = geo.detail(self.request({'ubigeo': '040104'}), 12290)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)['district'], 'Cerro Colorado')
            self.assertEqual(query.call_args.kwargs['where'], "OBJECTID=12290 AND ID_DIST='040104'")
            gallery.assert_called_once_with('04010484005007')
            self.assertEqual(geo.detail(self.request(), 12290).status_code, 404)
        parser = geo.GalleryParser('040104')
        parser.feed('<img src="/img_catastro/040104/84005007.jpg"><img src="/img_catastro/040126/07042018.jpg">')
        self.assertEqual(parser.images, ['https://catastro.cofopri.gob.pe/img_catastro/040104/84005007.jpg'])
