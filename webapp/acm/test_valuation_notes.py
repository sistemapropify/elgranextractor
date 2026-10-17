import io
import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase, SimpleTestCase

from .access import ACMAccess, ACMIdentity, DEFAULTS, policy_for
from .access_data import issue_snapshot, opaque_id, project
from .access_models import ACMPortalAnalysis, ACMRolePolicy
from .components_engine import candidates, calculate
from . import components_views
from .test_components import params, sample, _pdf_text


class ValuationNotesAccessTests(TestCase):
    def setUp(self):
        self.role = dict(id=20, name='Agente No Afiliado')
        flags, revision = policy_for(self.role)
        self.access = ACMAccess(ACMIdentity('77', 'fixture-agent'), self.role, self.role, flags, revision, '')
        self.rows = candidates(sample(), params())
        self.state = dict(user='77', params=params(), records=self.rows, warnings=[])
        self.factory = RequestFactory()

    def request(self, payload):
        request = self.factory.post('/acm/componentes/calcular/', data=json.dumps(payload), content_type='application/json')
        request.session = {}
        request.acm_access = self.access
        request.acm_identity = self.access.user
        request._dont_enforce_csrf_checks = True
        return request

    def payload(self, **changes):
        request = self.request({})
        return {'token': issue_snapshot(request, self.state), **changes}

    def test_basic_role_can_calibrate_and_store_its_justification(self):
        self.assertTrue(self.access.permissions['adjust_valuation'])
        self.assertTrue(self.access.permissions['report_notes'])
        response = components_views.save_history(self.request(self.payload(
            manual_valuation=234567.89, report_notes='  Mejoras recientes.\r\nBuena ubicacion.  ')))
        self.assertEqual(response.status_code, 200, response.content)
        saved = ACMPortalAnalysis.objects.get(owner_id='77').snapshot['params']
        self.assertEqual(saved['manual_valuation'], 234567.89)
        self.assertEqual(saved['report_notes'], 'Mejoras recientes.\nBuena ubicacion.')

    def test_explicit_role_restriction_is_still_respected(self):
        ACMRolePolicy.objects.create(role_id=20, permissions={'adjust_valuation': False, 'report_notes': False}, updated_by='1')
        self.access.permissions, _ = policy_for(self.role)
        for values in ({'manual_valuation':123456}, {'report_notes':'Observacion'}):
            response = components_views.recalculate(self.request(self.payload(**values)))
            self.assertEqual(response.status_code, 403)

    def test_restore_value_and_clear_notes_remove_previous_values(self):
        self.state['params'].update(manual_valuation=234567, report_notes='Anterior')
        request = self.request(self.payload(manual_valuation=None, report_notes=''))
        state, _ = components_views._signed_selection(request)
        self.assertNotIn('manual_valuation', state['params'])
        self.assertNotIn('report_notes', state['params'])

    def test_invalid_amounts_and_notes_are_rejected(self):
        for amount in (True, 'NaN', -1, 1000000001):
            response = components_views.recalculate(self.request(self.payload(manual_valuation=amount)))
            self.assertEqual(response.status_code, 400)
        for notes in (False, {'text':'bad'}, 'x'*10001, 'bad\x00text'):
            response = components_views.recalculate(self.request(self.payload(report_notes=notes)))
            self.assertEqual(response.status_code, 400)

    def test_restricted_notes_never_reach_report_projection(self):
        self.access.permissions['report_notes'] = False
        self.state['params']['report_notes'] = 'Private note'
        safe, _, _ = project(self.request({}), self.state)
        self.assertNotIn('report_notes', safe['params'])


class ValuationNotesReportTests(SimpleTestCase):
    def test_notes_reach_pdf_word_and_html_as_plain_text(self):
        from docx import Document
        from .components_pdf import build_acm_pdf
        from .components_report import build_acm_docx
        from .components_html import build_acm_html
        p = {**params(), 'property_type':'Casa', 'manual_valuation':234567.89, 'report_notes':'Mejoras recientes.\nObservacion <b>especial</b> & acceso.'}
        rows = candidates(sample(), p)
        result = calculate(rows, p)
        pdf = build_acm_pdf(p, rows, result, fetch_images=False)
        self.assertIn(b'Mejoras recientes.', _pdf_text(pdf))
        doc = Document(io.BytesIO(build_acm_docx(p, rows, result, fetch_images=False)))
        text = '\n'.join(paragraph.text for paragraph in doc.paragraphs)
        self.assertIn('Justificación u observaciones', text)
        self.assertIn(p['report_notes'], text)
        self.assertNotIn('ajustada manualmente', text)
        html = build_acm_html(p, rows, result)
        self.assertIn('Justificación u observaciones', html)
        self.assertIn('Observacion &lt;b&gt;especial&lt;/b&gt; &amp; acceso.', html)
        self.assertNotIn('ajustado en la tarjeta', html)
        self.assertIn('234,567.89', html)

    def test_empty_notes_do_not_create_empty_report_sections(self):
        from .components_html import build_acm_html
        rows = candidates(sample(), params())
        html = build_acm_html(params(), rows, calculate(rows, params()))
        self.assertNotIn('Justificación u observaciones', html)
