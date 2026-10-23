import copy
import hashlib
import io
import json
from unittest.mock import patch
from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase, RequestFactory, TestCase
from PIL import Image

from . import cadastral_views
from .access import DEFAULTS, policy_for
from .access_models import ACMRolePolicy
from catastro import master
from catastro.test_map_report import pages, LOT, RECORD


def archive():
    return {'lot_id': LOT, 'district_ubigeo': LOT[:6], 'extraction_revision': 2,
            'feature': {'attributes': {'AREA_TER': '9999', 'AREA_CON': '2012', 'NIVELES': 99}},
            'artifacts': [{'type': 'facade_image', 'filename': 'facade.jpg'}],
            'reports': [{'type': 'cadastral_report_pdf', 'record_id': RECORD, 'form_number': '1', 'pages': pages()}]}


class CadastralBasicPolicyTests(TestCase):
    role={'id':20,'name':'Agente No Afiliado'}

    def test_basic_role_includes_the_cadastre(self):
        self.assertTrue(policy_for(self.role)[0]['cadastral_info'])

    def test_existing_policy_without_new_flag_inherits_basic_access(self):
        ACMRolePolicy.objects.create(role_id=20,permissions={'pdm_polygons':False},updated_by='test')
        self.assertTrue(policy_for(self.role)[0]['cadastral_info'])

    def test_administrator_can_still_disable_it_for_a_specific_role(self):
        ACMRolePolicy.objects.create(role_id=20,permissions={'cadastral_info':False},updated_by='test')
        self.assertFalse(policy_for(self.role)[0]['cadastral_info'])


class CadastralAccessTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def request(self, allowed=True):
        request = self.factory.get('/acm/catastro/configuracion/')
        request.acm_access = SimpleNamespace(permissions={**DEFAULTS, 'cadastral_info': allowed})
        return request

    def test_cadastre_is_included_by_default_in_the_basic_acm(self):
        self.assertTrue(DEFAULTS['cadastral_info'])

    @patch('acm.cadastral_views.master.configuration')
    def test_forbidden_role_cannot_obtain_provider_configuration(self, config):
        self.assertEqual(cadastral_views.configuration(self.request(False)).status_code, 403)
        config.assert_not_called()

    @patch('acm.cadastral_views.master.lot_summary')
    @patch('acm.cadastral_views.master.archived_facade')
    def test_forbidden_role_cannot_obtain_lot_or_photo(self, photo, summary):
        self.assertEqual(cadastral_views.lot(self.request(False), LOT).status_code, 403)
        self.assertEqual(cadastral_views.facade(self.request(False), LOT).status_code, 403)
        photo.assert_not_called(); summary.assert_not_called()

    def test_anonymous_cannot_obtain_configuration(self):
        self.assertEqual(cadastral_views.configuration(self.factory.get('/')).status_code, 401)

    def test_allowed_configuration_is_small_and_contains_no_district_geometries(self):
        response = cadastral_views.configuration(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'coordinates', response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        import json
        config=json.loads(response.content)
        self.assertEqual(config['scope'],'radius')
        self.assertNotIn('max_lots',config)
        cayma=next(item for item in config['providers']
                   if item['id']=='cayma-pud-2006-eu03')
        self.assertTrue(cayma['reference_only'])
        self.assertFalse(cayma['contributes'])
        sector=next(item for item in config['providers']
                    if item['id']=='cayma-sector-32-provisional')
        self.assertTrue(sector['reference_only'])
        self.assertFalse(sector['contributes'])

    @patch('acm.cadastral_views.source_manager.store')
    @patch('acm.cadastral_views.source_manager.durable', return_value=True)
    @patch('acm.cadastral_views.source_manager.enabled', return_value=False)
    @patch('acm.cadastral_views.raster_overlays.list_all_overlays')
    def test_basic_role_receives_the_same_master_raster_catalog(
            self, overlays, enabled, durable, store):
        overlays.return_value = [{'id': 'drone-raster-a', 'ubigeo': '040126',
                                  'name': 'Dron Yanahuara'}]
        store.return_value = SimpleNamespace(revision=9)
        response = cadastral_views.raster_catalog(self.request())
        self.assertEqual(response.status_code, 200)
        import json
        item = json.loads(response.content)['overlays'][0]
        self.assertEqual(item['image_url'],
                         '/acm/catastro/raster/drone-raster-a/imagen/?ubigeo=040126')

    @patch('acm.cadastral_views.source_manager.store')
    @patch('acm.cadastral_views.source_manager.enabled', return_value=True)
    @patch('acm.cadastral_views.raster_overlays.image_body', return_value=(b'\xff\xd8test','image/jpeg'))
    def test_basic_role_can_read_the_master_raster_image(self, body, enabled, store):
        store.return_value = object()
        request = self.request()
        request.GET = {'ubigeo': '040126'}
        response = cadastral_views.raster_image(request, 'drone-raster-a')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertEqual(response.content, b'\xff\xd8test')

    @patch('catastro.source_manager.durable', return_value=True)
    @patch('catastro.master_d1.Gateway')
    def test_d1_master_record_exposes_gis_values_and_identity(self, gateway, durable):
        entity_id = '11111111-2222-4333-8444-555555555555'
        unit_id = '66666666-7777-4888-9999-aaaaaaaaaaaa'
        def read(sql, params=()):
            if 'FROM identities i' in sql and 'JOIN versions' in sql:
                return [{'entity_id': entity_id, 'ubigeo': LOT[:6],
                         'version_id': 'v1', 'source_id': 'geollaqta-040126',
                         'version_label': 'Tanda', 'sector': '02', 'block': '001',
                         'lot': '001', 'gis_land_area': 118.4,
                         'gis_built_area': 15.7, 'lot_floors': 2, 'lot_units': 1,
                         'address': 'Calle de prueba'}]
            if 'FROM relationships r' in sql:
                return [{'entity_id': unit_id, 'source_feature_id': RECORD,
                         'layer': 'unidad'}]
            if 'FROM current_attributes' in sql:
                return [{'entity_id': unit_id, 'land_area': 120,
                         'built_area': 14.33, 'floors': 2, 'units': 1,
                         'front': 10, 'back': 9, 'left': 8, 'right': 7,
                         'perimeter': 34}]
            if 'FROM media' in sql:
                return [{'id': 'facade-1', 'kind': 'facade_image'},
                        {'id': 'report-1', 'kind': 'cadastral_report_pdf'}]
            return []
        gateway.return_value.read.side_effect = read
        value = master.d1_lot_summary(LOT)
        self.assertEqual(value['master']['entity_id'], entity_id)
        self.assertEqual(value['master']['selected_entity_id'], unit_id)
        self.assertEqual(value['metrics']['land_area'], '120')
        self.assertEqual(value['metrics']['built_area'], '14.33')
        self.assertEqual(value['metrics']['perimeter'], '34')
        self.assertEqual(value['gis_metrics']['land_area'], '118.4')
        self.assertEqual(value['reports'][0]['record_id'], RECORD)
        self.assertEqual(value['facade_url'], '/acm/catastro/medios/facade-1/')

    @patch('acm.cadastral_views.master.d1_lot_summary')
    @patch('cuadrantizacion.geollaqta.report_response')
    def test_acm_merges_d1_master_values_with_report_evidence(self, report, d1):
        from django.http import JsonResponse
        report.return_value = JsonResponse({
            'lot_id': LOT, 'metrics': {'land_area': None, 'built_area': '20.5',
                'floors': None, 'units': None,
                'boundaries': {'frente': None, 'derecha': None,
                               'izquierda': None, 'fondo': None}},
            'reports': [{'record_id': RECORD, 'form_number': '3/5'}],
            'selected_record_id': RECORD, 'document_status': 'verified',
            'verified': True, 'facade_url': None,
        })
        d1.return_value = {
            'lot_id': LOT, 'metrics': {'land_area': '99', 'built_area': None,
                'floors': '2', 'units': '1',
                'boundaries': {'frente': '10', 'derecha': None,
                               'izquierda': None, 'fondo': None}},
            'gis_metrics': {'land_area': '99', 'built_area': '21'},
            'reports': [{'record_id': RECORD, 'form_number': ''}],
            'selected_record_id': RECORD, 'document_status': 'verified',
            'verified': True, 'source_label': 'Catastro Maestro · D1',
            'master': {'entity_id': '11111111-2222-4333-8444-555555555555'},
        }
        response = cadastral_views.lot(self.request(), LOT)
        value = json.loads(response.content)
        self.assertEqual(value['metrics']['land_area'], '99')
        self.assertEqual(value['metrics']['built_area'], '20.5')
        self.assertEqual(value['gis_metrics']['built_area'], '21')
        self.assertEqual(value['reports'][0]['form_number'], '3/5')
        self.assertEqual(value['source_label'], 'Catastro Maestro · D1')

    def test_invalid_lot_is_rejected_before_storage_access(self):
        with patch('catastro.master.manifest') as read:
            self.assertEqual(cadastral_views.lot(self.request(), '../../secret').status_code, 400)
            read.assert_not_called()

    @patch('catastro.master.archived_facade')
    def test_facade_is_image_bytes_and_never_a_pdf(self, read):
        stream = io.BytesIO(); Image.new('RGB', (2, 2)).save(stream, 'PNG'); read.return_value = stream.getvalue()
        response = cadastral_views.facade(self.request(), LOT)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertTrue(response.content.startswith(b'\xff\xd8'))

    @patch('catastro.master.manifest')
    def test_areas_perimeters_and_floors_never_fall_back_to_gis(self, read):
        read.return_value = archive()
        value = master.lot_summary(LOT)
        self.assertEqual(value['metrics']['land_area'], '200')
        self.assertEqual(value['metrics']['built_area'], '20.5')
        self.assertEqual(value['metrics']['boundaries']['frente'], '10')
        self.assertIsNone(value['metrics']['floors'])
        self.assertNotIn('87654321', str(value))
        self.assertNotIn('9999', str(value))

    @patch('catastro.master.manifest')
    def test_blank_document_value_stays_blank(self, read):
        read.return_value = archive();read.return_value['reports'][0]['pages'] = pages(land=None)
        self.assertIsNone(master.lot_summary(LOT)['metrics']['land_area'])

    @patch('catastro.master._download', side_effect=OSError('connection timed out'))
    @patch('catastro.master.manifest', return_value=None)
    def test_connection_failure_is_not_reported_as_a_blank_document(self, read, download):
        value = master.lot_summary(LOT)
        self.assertFalse(value['verified'])
        self.assertEqual(value['document_status'], 'unavailable')

    @patch('catastro.master.manifest')
    def test_report_of_another_lot_is_not_used(self, read):
        read.return_value = archive()
        read.return_value['reports'][0]['pages'][0]['named_fields'][2]['value'] = '999'
        value = master.lot_summary(LOT)
        self.assertFalse(value['verified'])
        self.assertIsNone(value['metrics']['land_area'])

    @patch('catastro.master.manifest')
    def test_multiple_units_are_not_added(self, read):
        read.return_value = archive()
        read.return_value['reports'].append({'type': 'cadastral_report_pdf', 'record_id': RECORD[:-1]+'3', 'form_number': '2', 'pages': pages(built='42.35')})
        self.assertEqual(master.lot_summary(LOT)['metrics']['built_area'], '20.5')
        self.assertEqual(master.lot_summary(LOT, RECORD[:-1]+'3')['metrics']['built_area'], '42.35')
        with self.assertRaises(ValueError): master.lot_summary(LOT, RECORD[:-1]+'9')

    @patch('catastro.master.manifest')
    def test_form_precedes_report_and_only_missing_fields_fall_back(self, read):
        read.return_value = archive()
        read.return_value['reports'].append({'type': 'individual_record_pdf', 'record_id': RECORD,
                                            'pages': pages(land='199', built=None)})
        result = master.lot_summary(LOT)['metrics']
        self.assertEqual(result['land_area'], '199')
        self.assertEqual(result['built_area'], '20.5')

    @patch('catastro.master._download', side_effect=OSError('offline'))
    @patch('catastro.master.manifest', return_value=None)
    def test_outage_keeps_explicit_unverified_fields_without_inventing_photo(self, read, download):
        result = master.lot_summary(LOT)
        self.assertIsNone(result['facade_url'])
        self.assertFalse(result['verified'])
        self.assertIsNone(result['metrics']['land_area'])

    @patch('catastro.master._download', side_effect=OSError('offline'))
    @patch('catastro.master.manifest')
    def test_old_extractions_are_not_trusted(self, read, download):
        read.return_value = archive();read.return_value['extraction_revision'] = 1
        self.assertFalse(master.lot_summary(LOT)['verified'])

    def test_photo_url_allowlist(self):
        self.assertTrue(master._facade_url('https://catastro.cofopri.gob.pe/img_catastro/'+LOT[:6]+'/example.jpg', LOT))
        self.assertFalse(master._facade_url('https://evil.test/img_catastro/'+LOT[:6]+'/example.jpg', LOT))


class SharedCadastralReportTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def quad(self, record=None):
        from cuadrantizacion.geollaqta import report
        request = self.factory.get('/', {'ubigeo': LOT[:6], **({'record_id': record} if record else {})})
        request.current_user = SimpleNamespace(is_active=True, is_authenticated=True)
        response = report(request, LOT)
        self.assertEqual(response.status_code, 200)
        import json
        return json.loads(response.content)

    @patch('catastro.master._download', side_effect=OSError('offline'))
    @patch('catastro.master.manifest', return_value=None)
    @patch('catastro.map_report._archived_reports')
    def test_acm_reuses_report_verified_in_quadrantizacion_even_when_source_is_offline(self, reports, manifest, download):
        reports.return_value = archive()['reports']
        expected = self.quad()
        result = master.lot_summary(LOT)
        self.assertEqual(result['document_status'], 'verified')
        self.assertEqual(result['metrics'], expected['metrics'])
        self.assertNotIn('87654321', str(result))
        download.assert_not_called()

    @patch('catastro.map_report._archived_reports', side_effect=AssertionError('should reuse verified report'))
    @patch('catastro.master.manifest')
    def test_quadrantizacion_reuses_report_verified_in_acm(self, manifest, reports):
        manifest.return_value = archive()
        expected = master.lot_summary(LOT)
        self.assertEqual(self.quad()['metrics'], expected['metrics'])
        reports.assert_not_called()

    @patch('catastro.master._download', side_effect=OSError('offline'))
    @patch('catastro.master.manifest', return_value=None)
    @patch('catastro.map_report._archived_reports')
    def test_cached_reports_remain_separate_for_each_unit(self, reports, manifest, download):
        second = RECORD[:-1] + '3'
        reports.return_value = archive()['reports'] + [{'type': 'cadastral_report_pdf', 'record_id': second,
                                                      'form_number': '2', 'pages': pages(built='42.35')}]
        self.quad()
        self.quad(second)
        self.assertEqual(master.lot_summary(LOT)['metrics']['built_area'], '20.5')
        self.assertEqual(master.lot_summary(LOT, second)['metrics']['built_area'], '42.35')
        download.assert_not_called()

    @patch('catastro.master.manifest')
    def test_shared_report_cache_does_not_override_available_individual_form(self, manifest):
        from catastro.map_report import report_measurements
        report_measurements(LOT, reports=archive()['reports'])
        manifest.return_value = archive()
        manifest.return_value['reports'].append({'type': 'individual_record_pdf', 'record_id': RECORD,
                                                 'pages': pages(land='199', built=None)})
        self.assertEqual(master.lot_summary(LOT)['metrics']['land_area'], '199')
        self.assertEqual(master.lot_summary(LOT)['metrics']['built_area'], '20.5')


    @patch('catastro.map_report._archived_reports')
    @patch('catastro.master.lot_summary', side_effect=AssertionError('ACM must use the exact same handler as Cuadrantización'))
    def test_both_http_cards_return_identical_document_content_without_prometeo_login_in_acm(self, old, reports):
        reports.return_value = archive()['reports']
        request = self.factory.get('/acm/catastro/lotes/' + LOT + '/')
        request.acm_access = SimpleNamespace(permissions={**DEFAULTS, 'cadastral_info': True})
        acm = cadastral_views.lot(request, LOT)
        quad = self.quad()
        import json
        self.assertEqual(acm.status_code, 200)
        self.assertEqual(json.loads(acm.content), quad)
        self.assertEqual(acm['Cache-Control'], 'no-store')
        old.assert_not_called()

    @patch('cuadrantizacion.geollaqta.report_response')
    def test_shared_report_handler_remains_protected_by_active_acm_role(self, report):
        request = self.factory.get('/acm/catastro/lotes/' + LOT + '/')
        request.acm_access = SimpleNamespace(permissions={**DEFAULTS, 'cadastral_info': False})
        self.assertEqual(cadastral_views.lot(request, LOT).status_code, 403)
        report.assert_not_called()

    @patch('cuadrantizacion.geollaqta.report_response')
    def test_acm_requests_only_the_report_and_never_the_individual_ficha(self, report):
        request=self.factory.get('/acm/catastro/lotes/'+LOT+'/')
        request.acm_access=SimpleNamespace(permissions={**DEFAULTS,'cadastral_info':True})
        cadastral_views.lot(request,LOT)
        report.assert_called_once_with(LOT,LOT[:6],None,report_only=True)


    @patch('catastro.map_report.report_measurements', side_effect=RuntimeError('source offline'))
    @patch('catastro.master.lot_summary', side_effect=AssertionError('do not start an extra gallery query'))
    def test_http_cards_report_the_same_failure_and_allow_a_later_retry(self, old, reader):
        from cuadrantizacion.geollaqta import report
        request = self.factory.get('/acm/catastro/lotes/' + LOT + '/')
        request.acm_access = SimpleNamespace(permissions={**DEFAULTS, 'cadastral_info': True})
        acm = cadastral_views.lot(request, LOT)
        quad_request = self.factory.get('/', {'ubigeo': LOT[:6]})
        quad_request.current_user = SimpleNamespace(is_active=True, is_authenticated=True)
        quad = report(quad_request, LOT)
        self.assertEqual(acm.status_code, 502)
        self.assertEqual(acm.content, quad.content)
        reader.side_effect = None
        reader.return_value = {'lot_id': LOT, 'metrics': {'land_area': '200'}}
        self.assertEqual(cadastral_views.lot(request, LOT).status_code, 200)
        old.assert_not_called()
