"""Detail feature age must survive extraction and normalized field mapping."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from scrapi import adondevivir_scraper as adon
from scrapi.normalization import construction_age, urbania_row
from scrapi.paged_engine import enrich, normalize


FEATURES = ['112 m² tot.', '112 m² cub.', '2 baños', '3 dorm.', '13 años']


class DetailAgeTests(unittest.TestCase):
    def test_user_example_and_zero_in_portal_features(self):
        for age in (0, 1, 13, 150):
            for label in (f'{age} años', f'{age}\u00a0años', f'Antigüedad: {age} años'):
                with self.subTest(label=label):
                    actual, evidence = construction_age({'Caracteristicas': ' | '.join(FEATURES[:-1] + [label])})
                    self.assertEqual(actual, age)
                    self.assertEqual(evidence['source'], 'portal_age_field')
                    self.assertEqual(evidence['value'], label)

    def test_urbania_maps_years_to_age_field(self):
        row = urbania_row({'ID': '123456', 'Tipo': 'Departamento',
                           'Caracteristicas': ' | '.join(FEATURES)}, '2026-10-05')
        self.assertEqual(row['antiguedad_anios'], 13)
        self.assertEqual(row['datos_crudos']['_age_evidence']['value'], '13 años')

    def test_rejects_marketing_dates_ranges_and_conflicting_chips(self):
        for raw in (
            {'descripcion': '13 años'},
            {'Caracteristicas': '13 años de experiencia'},
            {'Caracteristicas': 'Entrega en 2027'},
            {'Caracteristicas': '10 a 13 años'},
            {'Caracteristicas': '13 años | 20 años'},
            {'Caracteristicas': '151 años'},
            {'Caracteristicas': 'A estrenar'},
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(construction_age(raw)[0])

    def test_explicit_age_mapping_preserves_zero(self):
        self.assertEqual(adon.mapear_a_formato_remax({'antiguedad': 0})['Antiguedad'], 0)
        self.assertEqual(normalize('adondevivir', adon, {'id': '123456', 'antiguedad': 13})['antiguedad_anios'], 13)


class AdonDetailExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_detail_chips_reach_normalized_age_without_changing_areas(self):
        url = 'https://www.adondevivir.com/propiedades/clasificado/veclapin-departamento-123456.html'
        page = SimpleNamespace(url=url, content=AsyncMock(return_value='<html></html>'),
            title=AsyncMock(return_value='Departamento en venta'),
            evaluate=AsyncMock(side_effect=['\n'.join(FEATURES), FEATURES]))
        raw = {'id': '123456', 'url': url, 'tipo': 'Departamento'}

        async def navigate(page, url, timeout):
            page._scraping_document_status = 200

        with patch.object(adon, 'navegar_con_cloudflare', side_effect=navigate), \
             patch.object(adon.asyncio, 'sleep', new=AsyncMock()):
            await enrich('adondevivir', adon, page, raw)
        row = normalize('adondevivir', adon, raw)
        self.assertEqual(row['antiguedad_anios'], 13)
        self.assertEqual(raw['_detail_area_labels'], {'total': 112.0, 'covered': 112.0})
        self.assertEqual(row['datos_crudos']['Caracteristicas'], ' | '.join(FEATURES))
        self.assertEqual(row['datos_crudos']['_age_evidence']['value'], '13 años')


if __name__ == '__main__':
    unittest.main()
