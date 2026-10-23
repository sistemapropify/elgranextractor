from copy import deepcopy
from types import SimpleNamespace

from django.test import SimpleTestCase, RequestFactory

from .components_engine import calculate, candidates, parameters
from .test_components import params, record, sample


class ReferenceFallbackTests(SimpleTestCase):
    def references(self, target='Departamento', count=8):
        p = parameters({**params(), 'property_type': target, 'built': 100})
        rows = candidates([record(str(i), kind=target, built=100, price=100000 + i * 10000,
                                 precision='aproximada', lat=p['lat'] + (20 + i * 25) / 111195)
                           for i in reversed(range(count))], p)
        return p, rows

    def test_fallback_is_automatic_nearest_five_and_uses_their_unit_prices(self):
        p, rows = self.references()
        before = deepcopy(rows)
        result = calculate(rows, p)
        self.assertTrue(result['reference_mode'])
        self.assertEqual(result['reference_display_ids'], ['0', '1', '2', '3', '4'])
        self.assertEqual(result['reference_ids'], ['0', '1', '2', '3', '4'])
        self.assertEqual(result['new']['total'], 120000)
        self.assertEqual(result['new']['unit'], 1200)
        self.assertEqual(len(result['breakdown']), 5)
        self.assertEqual(rows, before, 'The fallback must not erase quality issues or relabel references as comparables.')

    def test_deselecting_reference_recalculates_without_adding_sixth(self):
        p, rows = self.references()
        result = calculate(rows, p, ['0'])
        self.assertEqual(result['reference_display_ids'], ['0', '1', '2', '3', '4'])
        self.assertEqual(result['reference_ids'], ['1', '2', '3', '4'])
        self.assertEqual(result['new']['total'], 125000)
        self.assertIsNone(calculate(rows, p, [row['id'] for row in rows])['new'])

    def test_fewer_than_five_and_selected_radius_are_respected(self):
        p, rows = self.references(count=3)
        self.assertEqual(len(calculate(rows, p)['reference_ids']), 3)
        rows[0]['distance'] = 501
        result = calculate(rows, p)
        self.assertNotIn(rows[0]['id'], result['reference_display_ids'])

    def test_primary_comparables_always_take_precedence(self):
        p = parameters(params())
        result = calculate(candidates(sample(), p), p)
        self.assertNotIn('reference_mode', result)
        self.assertEqual(result['model'], 'components')

    def test_no_references_does_not_manufacture_a_value(self):
        p = parameters(params())
        result = calculate([], p)
        self.assertIsNone(result['new'])
        self.assertNotIn('reference_mode', result)

    def test_houses_without_soil_use_total_offer_per_built_area(self):
        p, rows = self.references('Casa', count=2)
        result = calculate(rows, p)
        self.assertEqual(result['model'], 'built')
        self.assertIsNone(result['land_unit'])
        self.assertEqual(result['new']['total'], 105000)
        self.assertNotIn('built_value', result['new'])

    def test_house_fallback_preserves_independent_soil_estimate_and_evidence(self):
        p, rows = self.references('Casa', count=2)
        rows += candidates([record('soil', 'Terreno', land=150, price=90000,
                                    lat=p['lat'] + 700 / 111195)], p)
        result = calculate(rows, p)
        self.assertTrue(result['reference_mode'])
        self.assertEqual(result['model'], 'built')
        self.assertEqual(result['land_unit'], 600)
        self.assertEqual(result['land_ids'], ['soil'])
        self.assertEqual(result['land_count'], 1)
        self.assertEqual(result['land_radius'], 1000)
        self.assertEqual(result['reference_display_ids'], ['0', '1'])
        self.assertEqual(result['new']['total'], 105000)
        self.assertNotIn('built_value', result['new'])
        self.assertTrue(any('no hay casas seleccionadas' in message for message in result['messages']))
        excluded = calculate(rows, p, ['soil'])
        self.assertIsNone(excluded['land_unit'])
        self.assertEqual(excluded['land_ids'], [])

    def test_soil_remains_available_when_all_house_references_are_deselected(self):
        p, rows = self.references('Casa', count=2)
        rows += candidates([record('soil', 'Terreno', land=150, price=90000)], p)
        result = calculate(rows, p, ['0', '1'])
        self.assertIsNone(result['new'])
        self.assertEqual(result['land_unit'], 600)
        self.assertEqual(result['land_ids'], ['soil'])

    def test_lands_and_old_houses_use_land_area_only(self):
        p = parameters({**params(), 'property_type': 'Terreno', 'land': 200, 'built': 0})
        rows = candidates([record('land', 'Terreno', land=100, price=100000, precision='aproximada')], p)
        result = calculate(rows, p)
        self.assertTrue(result['reference_mode'])
        self.assertEqual(result['new']['total'], 200000)
        old_house = parameters({**params(), 'age': 60, 'land': 200, 'built': 0})
        self.assertEqual(calculate(candidates([record('land', 'Terreno', land=100, price=100000,
                                                     precision='aproximada')], old_house), old_house)['new']['total'], 200000)

    def test_missing_numeric_data_rentals_contradictions_duplicates_and_quality_exclusions_do_not_calculate(self):
        p, rows = self.references(count=5)
        rows[0]['built'] = None
        rows[1]['operation'] = 'Alquiler'
        rows[2]['operation_status'] = 'review'
        rows[3]['duplicate_of'] = 'original'
        rows[4]['review_excluded'] = True
        self.assertIsNone(calculate(rows, p)['new'])

    def test_projection_hides_original_reference_ids_for_basic_roles(self):
        from .access_data import project
        from .access import DEFAULTS
        p, rows = self.references(count=2)
        request = RequestFactory().get('/')
        request.acm_access = SimpleNamespace(permissions=DEFAULTS, user=SimpleNamespace(pk=5),
                                            fingerprint='test', can_configure=False, previewing=False)
        client, result, _ = project(request, {'params': p, 'records': rows}, calculate(rows, p))
        self.assertEqual(set(result['reference_display_ids']), {row['id'] for row in client['records']})
        self.assertTrue(all(value.startswith('c-') for value in result['reference_ids']))
        self.assertNotIn('remax', str(result).lower())

    def test_reference_report_and_manual_adjustment_keep_the_same_value_and_notes(self):
        from .components_html import build_acm_html
        from .report_selection import report_unit_price
        p, rows = self.references(count=2)
        result = calculate(rows, p)
        p.update(manual_valuation=150000, report_notes='Estado de conservación revisado.',
                 report_ids=result['reference_display_ids'])
        html = build_acm_html(p, rows, result)
        self.assertIn('Mediana del precio por m² de las referencias', html)
        self.assertIn('Estado de conservación revisado.', html)
        self.assertIn('USD 150,000', html)
        self.assertEqual(report_unit_price(p, result), 1500)

    def test_pdf_and_word_include_reference_evidence_and_justification(self):
        import io
        import zipfile
        from unittest.mock import patch
        from .components_pdf import build_acm_pdf
        from .components_report import build_acm_docx
        from .test_components import _pdf_text
        p, rows = self.references(count=2)
        result = calculate(rows, p)
        p.update(manual_valuation=150000, report_notes='Conservacion revisada.',
                 report_ids=result['reference_display_ids'])
        with patch('acm.components_pdf._static_map', return_value=None):
            pdf = _pdf_text(build_acm_pdf(p, rows, result, fetch_images=False))
        self.assertIn(b'PROPIEDADES COMPARABLES', pdf)
        self.assertIn(b'REFERENCIAS', pdf)
        self.assertIn(b'150,000', pdf)
        self.assertIn(b'Conservacion revisada.', pdf)
        with zipfile.ZipFile(io.BytesIO(build_acm_docx(p, rows, result, fetch_images=False))) as archive:
            word = archive.read('word/document.xml').decode()
        self.assertIn('Conservacion revisada.', word)
        self.assertIn('150,000', word)
        self.assertIn('referencias más cercanas', word)

    def test_signed_search_and_recalculation_use_the_same_five_with_adjustment_and_notes(self):
        import json
        from unittest.mock import patch
        from .test_access_helpers import install_propify_fixture, client_selection
        from .access import get_access
        from .components_views import search, recalculate
        install_propify_fixture(self)
        p, rows = self.references()

        def request(payload):
            req = RequestFactory().post('/', content_type='application/json')
            req.current_user = SimpleNamespace(pk=5, is_authenticated=True, is_active=True)
            get_access(req)
            req._body = json.dumps(client_selection(req, payload)).encode()
            req._dont_enforce_csrf_checks = True
            return req

        with patch('acm.components_views.load_records', return_value=(rows, [])):
            response = search(request(p))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        ids = data['result']['reference_display_ids']
        self.assertEqual(len(ids), 5)
        response = recalculate(request({'token': data['token'], 'excluded': [ids[0]],
                                        'report_ids': ids[1:], 'manual_valuation': 140000,
                                        'report_notes': 'Justificación del agente.'}))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['result']['reference_display_ids'], ids)
        self.assertEqual(data['result']['new']['total'], 125000)
        self.assertEqual(data['params']['manual_valuation'], 140000)
        self.assertEqual(data['params']['report_notes'], 'Justificación del agente.')
