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
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(construction_age(raw)[0])

    def test_explicit_age_mapping_preserves_zero(self):
        self.assertEqual(adon.mapear_a_formato_remax({'antiguedad': 0})['Antiguedad'], 0)
        self.assertEqual(normalize('adondevivir', adon, {'id': '123456', 'antiguedad': 13})['antiguedad_anios'], 13)

    def test_same_integer_age_format_as_remax_and_urbania(self):
        from scrapi import remax_scraper as remax
        for age in (0, 7, 13):
            rows = (
                normalize('remax', remax, {'ID': '123456', 'Tipo': 'Departamento', 'Antiguedad': age}),
                normalize('adondevivir', adon, {'id': '123456', 'tipo': 'Departamento',
                    'Caracteristicas': f'62 m² tot. | {age} años'}),
                urbania_row({'ID': '123456', 'Tipo': 'Departamento',
                    'Caracteristicas': f'62 m² tot. | {age} años'}, '2026-10-05'),
            )
            for row in rows:
                with self.subTest(age=age, portal=row['fuente']):
                    self.assertIs(type(row['antiguedad_anios']), int)
                    self.assertEqual(row['antiguedad_anios'], age)

    def test_explicit_new_condition_is_zero_with_original_evidence(self):
        for label in ('A estrenar', 'de estreno', 'ESTRENO', ' A\u00a0estrenar ', 'Antigüedad: de estreno'):
            for key in ('Antiguedad', 'antiguedad', 'Antigüedad', 'Caracteristicas', 'caracteristicas'):
                with self.subTest(label=label, key=key):
                    age, evidence = construction_age({key: label})
                    self.assertIs(type(age), int)
                    self.assertEqual(age, 0)
                    self.assertEqual(evidence['value'], label.strip())
                    self.assertEqual(evidence['source'], 'portal_new_condition')
        self.assertEqual(construction_age({'description': 'Casa. Antigüedad: a estrenar.'})[0], 0)

    def test_numeric_age_and_build_year_override_new_condition(self):
        for raw, expected in (
            ({'Antiguedad': 7, 'Caracteristicas': 'De estreno'}, 7),
            ({'Antiguedad': 'A estrenar', 'Caracteristicas': '13 años'}, 13),
            ({'Tipo': 'Casa', 'Descripcion': 'Antigüedad: 7 años', 'Caracteristicas': 'Estreno'}, 7),
            ({'description': 'Casa construida en 2020', 'Caracteristicas': 'A estrenar'}, 6),
        ):
            with self.subTest(raw=raw):
                age, evidence = construction_age(raw, '2026-10-05')
                self.assertEqual(age, expected)
                self.assertEqual(evidence['condition_conflict'], 'numeric_age_overrides_new_condition')
        self.assertIsNone(construction_age({'Caracteristicas': '7 años | 13 años | A estrenar'})[0])

    def test_unknown_unfinished_marketing_and_invalid_age_are_not_zero(self):
        for raw in (
            {}, {'Antiguedad': ''}, {'Antiguedad': 'En construcción'},
            {'Antiguedad': 'En proyecto'}, {'Caracteristicas': 'Remodelada'},
            {'Caracteristicas': 'Como nueva'}, {'title': 'Casa de estreno'},
            {'description': 'Remodelada como nueva, cocina de estreno'},
            {'Antiguedad': 'No es de estreno'},
            {'Caracteristicas': 'A estrenar | En construcción'},
            {'Antiguedad': 151, 'Caracteristicas': 'A estrenar'},
            {'Caracteristicas': '10 a 20 años | Estreno'},
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(construction_age(raw)[0])

    def test_new_condition_same_integer_format_across_all_scrapers(self):
        from scrapi import remax_scraper as remax, properati_scraper as properati
        from scrapi.facebook_marketplace_scraper import standardize
        for label in ('A estrenar', 'de estreno', 'Estreno'):
            rows = (
                normalize('remax', remax, {'ID': '123456', 'Tipo': 'Casa', 'Antiguedad': label}),
                normalize('properati', properati, {'ID': '123456', 'Tipo': 'Casa', 'Antiguedad': label}),
                normalize('adondevivir', adon, {'id': '123456', 'tipo': 'Casa', 'Caracteristicas': label}),
                urbania_row({'ID': '123456', 'Tipo': 'Casa', 'Caracteristicas': label}, '2026-10-05'),
                standardize({'id': '123456', 'title': 'Casa', 'description': f'Antigüedad: {label}'}, '2026-10-05'),
            )
            for row in rows:
                with self.subTest(label=label, portal=row['fuente']):
                    self.assertIs(type(row['antiguedad_anios']), int)
                    self.assertEqual(row['antiguedad_anios'], 0)
                    self.assertIn('_age_evidence', row['datos_crudos'])


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
