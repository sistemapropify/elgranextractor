import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from scrapi import properati_scraper as source
from scrapi.paged_engine import normalize
from scrapi.properati_areas import detail_area


FEATURE = (Path(__file__).parent / 'fixtures/properati_cayma_220_features.html').read_text(encoding='utf8')


class ProperatiAreaTests(unittest.TestCase):
    def test_real_feature_wins_over_storage_room_and_similar_ads(self):
        html = '<div class="similar-snippet"><div class="place-details"><span data-test="area-value">999 m²</span></div></div>'
        html += FEATURE + '<p>2 cocheras. 1 depósito de 10 m².</p>'
        self.assertEqual(detail_area(html), 220)
        row = normalize('properati', source, {'ID': 'area-test', 'Tipo': 'Departamento', 'Area': '220 m²',
                                             'Descripcion': '1 depósito de 10 m²'})
        self.assertEqual(row['area_m2'], 220)
        self.assertEqual(row['area_construida'], 220)
        self.assertIsNone(row['area_terreno'])

    def test_missing_primary_surface_does_not_use_accessory(self):
        for description in ('1 depósito de 10 m²', 'Cochera de 12 m2', 'Terraza de 20 m²',
                            '10 m2 de depósito'):
            with self.subTest(description=description):
                row = normalize('properati', source, {'ID': 'area-test', 'Tipo': 'Departamento', 'Descripcion': description})
                self.assertIsNone(row['area_m2'])
        row = normalize('properati', source, {'ID': 'area-test', 'Tipo': 'Departamento',
                                             'Descripcion': 'Depósito de 10 m2. Departamento de 220 m2.'})
        self.assertEqual(row['area_m2'], 220)

    def test_absent_conflicting_and_duplicate_features(self):
        self.assertIsNone(detail_area('<p>Un depósito de 10 m²</p>'))
        self.assertIsNone(detail_area(FEATURE + FEATURE.replace('220 m²', '300 m²')))
        self.assertEqual(detail_area(FEATURE + FEATURE), 220)

    def test_legacy_scraped_unit_does_not_discard_main_area(self):
        for kind, field in [('Departamento', 'area_construida'), ('Terreno', 'area_terreno')]:
            row = normalize('properati', source, {'ID': 'legacy-area', 'Tipo': kind,
                                                 'Area': '220 mÂ²', 'Descripcion': '1 depósito de 10 m²'})
            self.assertEqual(row['area_m2'], 220)
            self.assertEqual(row[field], 220)

    def test_land_uses_its_main_surface(self):
        row = normalize('properati', source, {'ID': 'area-test', 'Tipo': 'Terreno', 'Area': '220 m²'})
        self.assertEqual(row['area_m2'], 220)
        self.assertEqual(row['area_terreno'], 220)
        self.assertIsNone(row['area_construida'])


class ProperatiDetailAreaTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_detail_overrides_incorrect_or_missing_listing_surface(self):
        for previous in ('', '10 m²'):
            page = SimpleNamespace(wait_for_timeout=AsyncMock(), content=AsyncMock(return_value=FEATURE),
                                   evaluate=AsyncMock(return_value={}))
            location = SimpleNamespace(wait_for=AsyncMock(), evaluate=AsyncMock(return_value=''))
            page.locator = lambda _: location
            raw = {'ID': 'area-test', 'Tipo': 'Departamento', 'Area': previous,
                   'Descripcion': '1 depósito de 10 m²',
                   'URL Propiedad': 'https://www.properati.com.pe/detalle/area-test'}
            with patch.object(source, 'navegar_con_cloudflare', new=AsyncMock()), \
                 patch.object(source, '_html_servidor', new=AsyncMock(return_value=FEATURE)), \
                 patch.object(source, 'extraer_coordenadas_desde_html', return_value=(-16.4, -71.5)), \
                 patch.object(source, '_precision_ubicacion_desde_html', return_value='exacta'):
                await source.extraer_detalle(page, raw)
            row = normalize('properati', source, raw)
            self.assertEqual(row['area_m2'], 220)
            self.assertEqual(row['datos_crudos']['_area_evidence']['source'], 'detail_feature')
