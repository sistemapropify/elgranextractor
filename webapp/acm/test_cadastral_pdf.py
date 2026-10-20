from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, RequestFactory
from django.urls import reverse, resolve
from acm.access import policy_for
from acm.access_models import ACMRolePolicy
from acm import cadastral_views
from catastro.test_map_report import LOT, RECORD, pages
from catastro.map_report import report_pdf
import hashlib


class CadastralPDFTests(SimpleTestCase):
    def request(self, pdf=False, info=True):
        request = RequestFactory().get('/acm/catastro/lotes/'+LOT+'/reporte.pdf', {'record_id': RECORD})
        request.acm_access = SimpleNamespace(permissions={'cadastral_info':info,'cadastral_pdf':pdf})
        return request

    @patch('catastro.map_report.report_pdf')
    def test_direct_pdf_requires_both_role_permissions(self, read):
        self.assertEqual(cadastral_views.report_pdf(self.request(), LOT).status_code, 403)
        self.assertEqual(cadastral_views.report_pdf(self.request(True, False), LOT).status_code, 403)
        self.assertEqual(cadastral_views.report_pdf(RequestFactory().get('/'), LOT).status_code, 401)
        read.assert_not_called()

    @patch('catastro.map_report.report_pdf', return_value=b'%PDF-original')
    def test_allowed_role_gets_original_pdf_inline_without_public_cache(self, read):
        response = cadastral_views.report_pdf(self.request(True), LOT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'%PDF-original')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        read.assert_called_once_with(LOT, RECORD)

    def test_pdf_uses_verified_r2_original_without_contacting_source(self):
        body = b'%PDF-verified-original'
        document = {'type':'cadastral_report_pdf','record_id':RECORD,'filename':'reporte.pdf',
                    '_archive_sha256':hashlib.sha256(body).hexdigest()}
        with patch('catastro.map_report.report_measurements', return_value={'selected_record_id':RECORD}), \
             patch('catastro.map_report._archived_reports', return_value=[document]), \
             patch('catastro.map_report.R2') as cloud, \
             patch('catastro.map_report.pdf_pages', return_value=pages()), \
             patch('catastro.map_report.download') as source:
            cloud.return_value.get.return_value = (body, {})
            self.assertEqual(report_pdf(LOT, RECORD), body)
            source.assert_not_called()

    @patch('catastro.map_report.report_pdf', side_effect=RuntimeError('unavailable'))
    def test_unavailable_pdf_is_not_reported_as_success(self, read):
        self.assertEqual(cadastral_views.report_pdf(self.request(True), LOT).status_code, 502)


class BasicCadastralPDFTests(TestCase):
    @patch('catastro.map_report.report_pdf', return_value=b'%PDF-original')
    def test_basic_roles_can_open_original_pdf_by_default(self, read):
        url = reverse('acm:cadastral_report_pdf', args=[LOT])
        self.assertEqual(resolve(url).func, cadastral_views.report_pdf)
        for role_id, name in ((2, 'Agente Interno'), (20, 'Agente No Afiliado'),
                              (8, 'Gerente General'), (22, 'Desarrollador de Proyectos')):
            with self.subTest(role=name):
                permissions, _ = policy_for({'id': role_id, 'name': name})
                self.assertTrue(permissions['cadastral_pdf'])
                request = RequestFactory().get(url, {'record_id': RECORD})
                request.acm_access = SimpleNamespace(permissions=permissions)
                response = cadastral_views.report_pdf(request, LOT)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b'%PDF-original')
                self.assertIn('inline;', response['Content-Disposition'])

    def test_existing_basic_policy_inherits_pdf_access(self):
        ACMRolePolicy.objects.create(role_id=20, permissions={'reports': False}, updated_by='1')
        permissions, _ = policy_for({'id': 20, 'name': 'Agente No Afiliado'})
        self.assertTrue(permissions['cadastral_info'])
        self.assertTrue(permissions['cadastral_pdf'])
        self.assertFalse(permissions['reports'])
