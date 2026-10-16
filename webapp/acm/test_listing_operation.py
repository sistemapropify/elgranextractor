from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from .components_engine import candidates, calculate, parameters
from .components_views import scraped_rows
from .listing_operation import resolve_operation
from .test_components import params, record


class OperationEvidenceTests(SimpleTestCase):
    def test_reported_cayma_rental_is_not_a_sale_comparable_or_reference(self):
        row = record('properati-1170', kind='Departamento', price=2600 / 3.44,
                     land=None, built=65, title='Departamento en Venta - Cayma',
                     _operation_title='Departamento en Alquiler en Cayma')
        p = parameters({**params(), 'property_type': 'Departamento', 'land': 0, 'built': 100})
        self.assertEqual(resolve_operation(row), ('Alquiler', 'confirmed'))
        self.assertEqual(candidates([row], p), [])

    def test_detail_url_ignores_search_query_and_uses_word_boundaries(self):
        sale = record('sale', title='Departamento con ventanas amplias',
                      url='https://example.com/departamento-en-venta?related=alquiler')
        self.assertEqual(resolve_operation(sale), ('Venta', 'confirmed'))
        rent = record('rent', url='https://example.com/propiedades/alclapna-departamento')
        self.assertEqual(resolve_operation(rent), ('Alquiler', 'confirmed'))

    def test_conflicting_explicit_detail_evidence_is_review_only(self):
        row = record('conflict', title='Casa', _operation_title='Casa en venta',
                     url='https://example.com/casa-en-alquiler')
        self.assertEqual(resolve_operation(row), ('No especificado', 'review'))
        rows = candidates([row], params())
        self.assertEqual(len(rows), 1)
        self.assertTrue(any('contradictoria' in issue for issue in rows[0]['issues']))
        self.assertFalse(calculate(rows, params())['house_ids'])

    def test_cheap_price_never_relabels_a_declared_sale_as_rental(self):
        row = record('cheap', price=756)
        self.assertEqual(resolve_operation(row), ('Venta', 'declared'))

    def test_unknown_and_dual_operation_never_value_a_sale(self):
        unknown = record('unknown', operation=None)
        mixed = record('mixed', title='Casa en venta o alquiler')
        rows = candidates([unknown, mixed], params())
        self.assertEqual([r['id'] for r in rows], ['unknown'])
        self.assertTrue(rows[0]['issues'])
        self.assertFalse(calculate(rows, params())['house_ids'])

    def test_calculation_does_not_trust_a_stale_empty_issue_list(self):
        rental = record('rent', kind='Departamento', operation='Alquiler', issues=[], distance=10)
        p = parameters({**params(), 'property_type': 'Departamento'})
        result = calculate([rental], p)
        self.assertFalse(result['house_ids'])
        self.assertIsNone(result['new'])


class StoredOperationTests(TestCase):
    def test_loader_uses_original_title_without_changing_stored_record(self):
        from ingestas.models import PropiedadesCompetencia
        stored = PropiedadesCompetencia.objects.create(
            fuente='properati', id_origen='operation-fixture', titulo='Departamento en Venta - Cayma',
            tipo_inmueble='Departamento', tipo_operacion='Venta', precio_soles=2600,
            area_construida=65, latitud=-16.4, longitud=-71.5,
            datos_crudos={'Titulo': 'Departamento en Alquiler en Cayma'})
        with patch('cuadrantizacion.views._map_image_url', return_value=''):
            rows = list(scraped_rows({**params(), 'sources': ['properati']}))
        self.assertEqual(resolve_operation(rows[0]), ('Alquiler', 'confirmed'))
        stored.refresh_from_db()
        self.assertEqual(stored.tipo_operacion, 'Venta')


class ProperatiOperationTests(SimpleTestCase):
    def test_adapter_preserves_rental_from_original_title(self):
        from scrapi.properati_scraper import mapear_a_formato_remax, estandarizar
        raw = {'ID': 'fixture', 'Tipo Propiedad': 'Departamento',
               'Titulo': 'Departamento en Alquiler en Cayma', 'Precio': 'S/.2,600', 'Area': '65 m²'}
        mapped = mapear_a_formato_remax(raw)
        self.assertEqual(mapped['Tipo'], 'Departamento en Alquiler')
        self.assertEqual(estandarizar(mapped, '2026-10-15')['tipo_operacion'], 'Alquiler')

    def test_adapter_does_not_default_an_unknown_operation_to_sale(self):
        from scrapi.properati_scraper import mapear_a_formato_remax, clasificar_operacion
        mapped = mapear_a_formato_remax({'Tipo Propiedad': 'Departamento', 'Titulo': 'Departamento en Cayma'})
        self.assertIsNone(clasificar_operacion(mapped['Tipo']))
