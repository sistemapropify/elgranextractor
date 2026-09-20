"""Pruebas de contrato y sesión, sin consultas ni escrituras en bases de datos."""
from types import SimpleNamespace
from django.test import SimpleTestCase, RequestFactory
from django.middleware.csrf import get_token
from rest_framework.request import Request
from rest_framework.parsers import MultiPartParser
from rest_framework.exceptions import PermissionDenied
from .serializers import ZonaValorSerializer
from .views import PrometeoSessionAuthentication


class GuardadoCuadranteTests(SimpleTestCase):
    def test_accepts_map_pairs_and_quadrant_level(self):
        serializer = ZonaValorSerializer(data={
            'nombre_zona': 'Cuadrante de prueba', 'nivel': 'cuadrante',
            'coordenadas': [[-16.4, -71.5], [-16.41, -71.5], [-16.4, -71.51]],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_invalid_coordinates_without_server_error(self):
        for coords in ([['bad', 0], [0, 1], [1, 0]],
                       [[True, 0], [0, 1], [1, 0]],
                       [[float('nan'), 0], [0, 1], [1, 0]],
                       [[0, 0], [0, 0], [1, 1]]):
            with self.subTest(coords=coords):
                serializer = ZonaValorSerializer(data={'nombre_zona': 'Test', 'coordenadas': coords})
                self.assertFalse(serializer.is_valid())
                self.assertIn('coordenadas', serializer.errors)

    def test_custom_session_with_csrf_is_authenticated(self):
        raw = RequestFactory().post('/cuadrantizacion/zonas/')
        raw.current_user = SimpleNamespace(is_active=True, is_authenticated=True)
        token = get_token(raw)
        raw.COOKIES['csrftoken'] = raw.META['CSRF_COOKIE']
        raw.META['HTTP_X_CSRFTOKEN'] = token
        user, _ = PrometeoSessionAuthentication().authenticate(Request(raw, parsers=[MultiPartParser()]))
        self.assertIs(user, raw.current_user)

    def test_custom_session_without_csrf_is_rejected(self):
        raw = RequestFactory().post('/cuadrantizacion/zonas/')
        raw.current_user = SimpleNamespace(is_active=True)
        with self.assertRaises(PermissionDenied):
            PrometeoSessionAuthentication().authenticate(Request(raw))

    def test_missing_session_is_not_authenticated(self):
        raw = RequestFactory().post('/cuadrantizacion/zonas/')
        self.assertIsNone(PrometeoSessionAuthentication().authenticate(Request(raw)))
