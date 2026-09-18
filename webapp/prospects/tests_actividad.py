"""Pruebas del seguimiento de actividad del módulo de prospección."""

import types
from datetime import datetime

from django.test import SimpleTestCase, TestCase

from .models import ActivityLog
from .views import _rango_actividad, agrupar_actividad_por_hora, registrar_actividad


class AgrupacionActividadTests(SimpleTestCase):
    """La actividad se reparte en las 24 franjas horarias del día."""

    def test_genera_24_bandas(self):
        bandas = agrupar_actividad_por_hora([])
        self.assertEqual(len(bandas), 24)
        self.assertEqual(bandas[0]['label'], '00:00')
        self.assertEqual(bandas[23]['label'], '23:00')
        self.assertTrue(all(b['total'] == 0 for b in bandas))

    def test_reparte_por_hora(self):
        eventos = [
            {'hora': 0, 'descripcion': 'medianoche'},
            {'hora': 9, 'descripcion': 'mañana'},
            {'hora': 9, 'descripcion': 'otra mañana'},
            {'hora': 23, 'descripcion': 'noche'},
        ]
        bandas = agrupar_actividad_por_hora(eventos)
        self.assertEqual(bandas[0]['total'], 1)
        self.assertEqual(bandas[9]['total'], 2)
        self.assertEqual(bandas[23]['total'], 1)
        self.assertEqual(bandas[10]['total'], 0)
        self.assertEqual(len(bandas[9]['eventos']), 2)

    def test_ignora_horas_invalidas(self):
        bandas = agrupar_actividad_por_hora(
            [{'hora': None}, {'hora': 99}, {'hora': -1}, 'no-dict', None]
        )
        self.assertEqual(sum(b['total'] for b in bandas), 0)

    def test_rango_fechas(self):
        inicio, fin = _rango_actividad('2026-09-18', '2026-09-18')
        self.assertEqual(inicio.date(), datetime(2026, 9, 18).date())
        self.assertEqual((fin - inicio).days, 1)

    def test_rango_fechas_invalidas(self):
        self.assertEqual(_rango_actividad('', 'ayer'), (None, None))


class RegistrarActividadTests(TestCase):
    """El alta de eventos guarda usuario, tipo, descripción y user agent."""

    class _Peticion:
        def __init__(self, username='valery', path='/prospects/metricas/', ua='Mozilla/5.0'):
            self.propify_user = types.SimpleNamespace(username=username)
            self.user = types.SimpleNamespace(username=username)
            self.path = path
            self.META = {'HTTP_USER_AGENT': ua}

    def test_registra_evento(self):
        registrar_actividad(self._Peticion(), 'acceso', 'Ingresó al dashboard de métricas.')
        fila = ActivityLog.objects.get()
        self.assertEqual(fila.user_username, 'valery')
        self.assertEqual(fila.event_type, 'acceso')
        self.assertIn('Ingresó al dashboard', fila.description)
        self.assertIn('Mozilla', fila.user_agent)
        self.assertEqual(fila.path, '/prospects/metricas/')

    def test_tipo_desconocido_cae_en_otro(self):
        registrar_actividad(self._Peticion(), 'tipo_inventado', 'Prueba.')
        self.assertEqual(ActivityLog.objects.get().event_type, 'otro')

    def test_limita_user_agent(self):
        registrar_actividad(self._Peticion(ua='x' * 900), 'otro', 'Prueba.')
        self.assertLessEqual(len(ActivityLog.objects.get().user_agent), 400)

    def test_sin_usuario_usa_anonimo(self):
        peticion = self._Peticion()
        peticion.propify_user = None
        peticion.user = None
        registrar_actividad(peticion, 'otro', 'Prueba.')
        self.assertEqual(ActivityLog.objects.get().user_username, 'anonimo')

    def test_descripcion_se_normaliza(self):
        registrar_actividad(self._Peticion(), 'otro', '  muchas    espacios \n y saltos  ')
        self.assertEqual(ActivityLog.objects.get().description, 'muchas espacios y saltos')
