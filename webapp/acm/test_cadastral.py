import copy
import hashlib
import io
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
