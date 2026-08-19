from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


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
        self.assertIn('google.maps.drawing &&', self.source)
        self.assertIn('loadZones();', self.source)

    def test_map_initialization_is_idempotent(self):
        self.assertIn('if (mapInitializationStarted) return;', self.source)

    def test_refresh_clears_previous_zone_overlays(self):
        self.assertIn('renderedZoneOverlays', self.source)
        self.assertIn('overlay.setMap(null);', self.source)
