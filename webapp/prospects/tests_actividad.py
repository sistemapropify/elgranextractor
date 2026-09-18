"""Pruebas del seguimiento de actividad del módulo de prospección."""

import json
import types
from datetime import datetime, timedelta

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from .models import ActivityLog
from .views import (
    _rango_actividad,
    agrupar_actividad_por_hora,
    api_actividad,
    registrar_actividad,
)


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


class DiaUnicoTests(SimpleTestCase):
    """El filtro de un solo día tiene prioridad sobre desde/hasta."""

    def test_dia_tiene_prioridad_sobre_el_rango(self):
        inicio, fin = _rango_actividad('2026-01-01', '2026-12-31', dia='2026-09-18')
        self.assertEqual(inicio.date(), datetime(2026, 9, 18).date())
        self.assertEqual((fin - inicio).days, 1)

    def test_dia_invalido_usa_el_rango(self):
        inicio, fin = _rango_actividad('2026-09-18', '2026-09-18', dia='ayer')
        self.assertEqual(inicio.date(), datetime(2026, 9, 18).date())
        self.assertEqual((fin - inicio).days, 1)

    def test_sin_filtros_no_acota_el_rango(self):
        self.assertEqual(_rango_actividad('', '', dia=''), (None, None))


class ApiActividadTests(TestCase):
    """El endpoint acepta un único día y devuelve las 24 franjas horarias."""

    databases = {'default'}

    def setUp(self):
        self.factory = RequestFactory()

    def _consultar(self, username='valery', **params):
        peticion = self.factory.get('/prospects/api/actividad/', params)
        peticion.propify_user = types.SimpleNamespace(username=username, profile={})
        respuesta = api_actividad.__wrapped__(peticion)
        return json.loads(respuesta.content)

    def test_solo_devuelve_el_dia_pedido(self):
        hoy = timezone.localtime()
        ayer = hoy - timedelta(days=1)
        actual = ActivityLog.objects.create(
            user_username='valery', event_type='acceso', description='Evento de hoy.',
        )
        previo = ActivityLog.objects.create(
            user_username='valery', event_type='acceso', description='Evento de ayer.',
        )
        ActivityLog.objects.filter(pk=previo.pk).update(created_at=ayer)

        datos = self._consultar(dia=hoy.date().isoformat())
        self.assertTrue(datos['ok'])
        self.assertEqual(datos['total'], 1)
        self.assertEqual(datos['eventos'][0]['id'], actual.pk)
        self.assertEqual(datos['eventos'][0]['descripcion'], 'Evento de hoy.')
        self.assertEqual(datos['dia_label'], hoy.strftime('%d/%m/%Y'))
        self.assertEqual(datos['dia'], hoy.date().isoformat())
        self.assertEqual(len(datos['bandas']), 24)
        self.assertEqual(sum(b['total'] for b in datos['bandas']), 1)

    def test_dia_sin_eventos_devuelve_bandas_vacias(self):
        datos = self._consultar(dia=(timezone.localdate() - timedelta(days=3)).isoformat())
        self.assertEqual(datos['total'], 0)
        self.assertEqual(len(datos['bandas']), 24)
        self.assertTrue(all(b['total'] == 0 for b in datos['bandas']))

    def test_registra_evento_por_post(self):
        peticion = self.factory.post('/prospects/api/actividad/', {
            'event_type': 'filtro',
            'description': 'Aplicó filtros en Actividades: día=2026-09-18.',
            'path': '/prospects/metricas/',
        })
        peticion.propify_user = types.SimpleNamespace(username='valery', profile={})
        respuesta = api_actividad.__wrapped__(peticion)
        self.assertEqual(respuesta.status_code, 200)
        fila = ActivityLog.objects.get()
        self.assertEqual(fila.event_type, 'filtro')
        self.assertEqual(fila.user_username, 'valery')

    def test_post_sin_descripcion_no_guarda(self):
        peticion = self.factory.post('/prospects/api/actividad/', {'event_type': 'filtro'})
        peticion.propify_user = types.SimpleNamespace(username='valery', profile={})
        respuesta = api_actividad.__wrapped__(peticion)
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(ActivityLog.objects.count(), 0)
