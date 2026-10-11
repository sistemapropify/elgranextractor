import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from scrapi import properati_scraper as source
from scrapi.normalization import construction_age
from scrapi.paged_engine import normalize
from scrapi.properati_age import construction_features_from_html


FEATURE = '<div class="property__feature"><span>Año de construcción</span><span>2006</span></div>'


class ProperatiAgeTests(unittest.TestCase):
    def test_year_label_and_sibling_value_are_extracted(self):
        for html in (FEATURE, FEATURE.replace('Año', 'A&ntilde;o').replace('construcción', 'construcci&oacute;n'),
                     '<li>Año de construcción: 2006</li>'):
            self.assertEqual(construction_features_from_html(html), [2006])

    def test_other_listings_scripts_and_marketing_dates_are_excluded(self):
        html = '<div class="recommended-properties">' + FEATURE.replace('2006', '2020') + '</div>'
        html += '<script>"Año de construcción 1990"</script><p>Publicado en 2024</p>'
        self.assertEqual(construction_features_from_html(html + FEATURE), [2006])
        self.assertEqual(construction_features_from_html(html), [])

    def test_normalization_and_standalone_export_store_twenty_years(self):
        raw = {'ID': 'properati-age', 'Tipo': 'Departamento', 'Anio Construccion': [2006]}
        with patch('scrapi.paged_engine.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 11, tzinfo=timezone.utc)
            row = normalize('properati', source, raw)
        self.assertEqual(row['antiguedad_anios'], 20)
        self.assertEqual(row['datos_crudos']['_age_evidence']['year'], 2006)
        mapped = source.mapear_a_formato_remax(raw)
        self.assertEqual(source.estandarizar(mapped, '2027-01-01')['antiguedad_anios'], 21)

    def test_invalid_and_conflicting_years_are_not_saved_as_age(self):
        for values in ([2027], [1800], [2006, 2010], ['no informado']):
            self.assertIsNone(construction_age({'Anio Construccion': values}, '2026-10-11')[0])
        self.assertEqual(construction_age({'Anio Construccion': [2026]}, '2026-10-11')[0], 0)

    def test_existing_explicit_age_survives_mapping(self):
        for age in (0, 7, 20):
            mapped = source.mapear_a_formato_remax({'Antiguedad': age})
            self.assertEqual(source.estandarizar(mapped, '2026-10-11')['antiguedad_anios'], age)


class ProperatiDetailAgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_detail_extraction_keeps_the_original_year(self):
        page = SimpleNamespace(wait_for_timeout=AsyncMock(), content=AsyncMock(return_value=FEATURE),
                               evaluate=AsyncMock(return_value={}))
        location = SimpleNamespace(wait_for=AsyncMock(), evaluate=AsyncMock(return_value=''))
        page.locator = lambda _: location
        raw = {'ID': 'properati-age', 'URL Propiedad': 'https://www.properati.com.pe/detalle/test'}
        with patch.object(source, 'navegar_con_cloudflare', new=AsyncMock()), \
             patch.object(source, '_html_servidor', new=AsyncMock(return_value=FEATURE)), \
             patch.object(source, 'extraer_coordenadas_desde_html', return_value=(-16.4, -71.5)), \
             patch.object(source, '_precision_ubicacion_desde_html', return_value='exacta'):
            await source.extraer_detalle(page, raw)
        self.assertEqual(raw['Anio Construccion'], [2006])
        self.assertEqual(construction_age(raw, '2026-10-11')[0], 20)
