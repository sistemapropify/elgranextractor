from types import SimpleNamespace
from django.test import TestCase, RequestFactory
from .map_layers import map_layers_config, map_layers_api
from .models import CapaVectorialMapa, CapaRasterMapa, ZonaValor


class SharedMapLayersTests(TestCase):
    def test_new_active_layers_and_zone_edits_are_in_shared_config(self):
        vector = CapaVectorialMapa.objects.create(nombre='Nueva capa', geojson_url='new.geojson')
        hidden = CapaVectorialMapa.objects.create(nombre='Inactiva', geojson_url='hidden.geojson', activo=False)
        raster = CapaRasterMapa.objects.create(nombre='Plano nuevo', imagen_url='new.png')
        legacy = CapaRasterMapa.objects.create(nombre='PNG antiguo', imagen_url='cuadrantizacion/capas/zonificacion_pdm_2016_2025.png')
        zone = ZonaValor.objects.create(nombre_zona='Cuadrante', nivel='subzona',
            coordenadas=[[-16.4, -71.5], [-16.41, -71.5], [-16.4, -71.51]], color_fill='#ff0000', opacidad=0)
        config = map_layers_config()
        self.assertIn(vector.pk, [layer['id'] for layer in config['vectoriales']])
        self.assertNotIn(hidden.pk, [layer['id'] for layer in config['vectoriales']])
        self.assertIn(raster.pk, [layer['id'] for layer in config['raster']])
        self.assertNotIn(legacy.pk, [layer['id'] for layer in config['raster']])
        row = next(item for item in config['zonas'] if item['id'] == zone.pk)
        self.assertEqual(row['opacidad'], 0)
        self.assertEqual(row['color_fill'], '#ff0000')
        zone.color_fill = '#00ff00'; zone.save(update_fields=['color_fill'])
        self.assertEqual(next(item for item in map_layers_config()['zonas'] if item['id'] == zone.pk)['color_fill'], '#00ff00')
        self.assertEqual(map_layers_config(include_zones=False)['zonas'], [])

    def test_refresh_requires_auth_and_is_not_cached(self):
        request = RequestFactory().get('/cuadrantizacion/capas-mapa/')
        self.assertEqual(map_layers_api(request).status_code, 401)
        request.current_user = SimpleNamespace(is_active=True, is_authenticated=True)
        response = map_layers_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
