import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase

from . import views


class MapaZonasTemplateTests(SimpleTestCase):
    def setUp(self):
        self.template_path = (
            Path(settings.BASE_DIR)
            / 'templates'
            / 'cuadrantizacion'
            / 'mapa_zonas.html'
        )
        self.source = self.template_path.read_text(encoding='utf-8')

    def test_template_compiles(self):
        self.assertIsNotNone(get_template('cuadrantizacion/mapa_zonas.html'))

    def test_existing_zones_do_not_depend_on_removed_drawing_library(self):
        self.assertNotIn('libraries=drawing', self.source)
        self.assertIn('installPolygonTool(map);', self.source)
        self.assertIn('loadZones();', self.source)

    def test_map_initialization_is_idempotent(self):
        self.assertIn('if (mapInitializationStarted) return;', self.source)

    def test_refresh_clears_previous_zone_overlays(self):
        self.assertIn('renderedZoneOverlays', self.source)
        self.assertIn('overlay.setMap(null);', self.source)

    def test_available_propify_layer_uses_existing_branded_pin(self):
        self.assertIn('toggle-propify-properties', self.source)
        self.assertIn('Pin-propify.png', self.source)
        self.assertIn('PROPIFY_PROPERTIES_ENDPOINT', self.source)
        self.assertIn('Propify · Disponible', self.source)

    def test_propify_markers_have_type_district_filters_and_draggable_card(self):
        self.assertIn('propify-type-filter', self.source)
        self.assertIn('propify-district-filter', self.source)
        self.assertIn('propify-operation-filter', self.source)
        self.assertIn('setupDraggablePropifyCard()', self.source)
        self.assertIn('width: 84px;', self.source)
        self.assertIn("className: 'propify-price-label'", self.source)
        self.assertIn("+ '/m²'", self.source)

    def test_save_error_parser_accepts_html_server_errors(self):
        self.assertIn('function parseJsonResponse(response)', self.source)
        self.assertIn("El servidor respondió ' + response.status", self.source)


class AvailablePropifyPropertiesApiTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get(
            '/cuadrantizacion/propiedades-propify-disponibles/'
        )

    @patch('cuadrantizacion.views._available_propify_properties')
    def test_returns_only_payload_produced_by_available_filter(self, available_properties):
        available_properties.return_value = [{
            'id': 14,
            'code': 'P-014',
            'title': 'Casa disponible',
            'price': '150000.00',
            'address': 'Cayma',
            'property_type': 'Casa',
            'operation_type': 'Venta',
            'is_rental': False,
            'district': 'Cayma',
            'image_url': 'https://example.test/casa.jpg',
            'currency_symbol': '$',
            'price_per_m2': '833.33',
            'price_per_m2_usd': None,
            'built_area_m2': '180.00',
            'land_area_m2': '200.00',
            'area_used': 'built_area',
            'lat': -16.35,
            'lng': -71.54,
            'status': 'Disponible',
        }]

        response = views.api_propify_available_properties(self.request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['status_filter'], 'Disponible')
        self.assertEqual(payload['properties'][0]['code'], 'P-014')

    @patch(
        'cuadrantizacion.views._available_propify_properties',
        side_effect=RuntimeError('database unavailable'),
    )
    def test_database_failure_returns_json_instead_of_html(self, _available_properties):
        response = views.api_propify_available_properties(self.request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload['properties'], [])
        self.assertIn('error', payload)

    def test_rental_uses_total_price_instead_of_price_per_square_meter(self):
        operation, is_rental = views._normalize_propify_operation('Arrendamiento')

        self.assertEqual(operation, 'Alquiler')
        self.assertTrue(is_rental)
        self.assertIsNone(
            views._sale_price_per_m2('1400.00', '100.00', is_rental=True)
        )

    def test_sale_normalizes_operation_and_calculates_price_per_square_meter(self):
        operation, is_rental = views._normalize_propify_operation('Compra')

        self.assertEqual(operation, 'Venta')
        self.assertFalse(is_rental)
        self.assertEqual(
            views._sale_price_per_m2('150000.00', '100.00', is_rental=False),
            '1500.00',
        )

    def test_sol_price_per_square_meter_is_converted_at_fixed_rate(self):
        self.assertEqual(
            views._price_per_m2_in_usd('3440.00', currency_id=2),
            '1000.00',
        )
        self.assertIsNone(
            views._price_per_m2_in_usd('3440.00', currency_id=1)
        )


class ZonaValorCreateTests(SimpleTestCase):
    @patch('cuadrantizacion.views.calcular_area_poligono', return_value=Decimal('125.50'))
    def test_create_saves_polygon_without_running_price_calculation(self, area_calculator):
        zone = SimpleNamespace(
            id=7,
            nivel='cuadrante',
            coordenadas=[[-16.4, -71.5], [-16.4, -71.4], [-16.3, -71.4]],
            area_total=None,
            save=Mock(),
        )
        serializer = Mock()
        serializer.save.return_value = zone
        view = views.ZonaValorViewSet()
        view.request = SimpleNamespace(
            current_user=SimpleNamespace(username='tester')
        )

        # Bypass only transaction.atomic's wrapper; the create logic itself is tested.
        views.ZonaValorViewSet.perform_create.__wrapped__(view, serializer)

        area_calculator.assert_called_once_with(zone.coordenadas)
        zone.save.assert_called_once_with(
            update_fields=['area_total', 'fecha_actualizacion']
        )
        self.assertEqual(zone.area_total, Decimal('125.50'))
