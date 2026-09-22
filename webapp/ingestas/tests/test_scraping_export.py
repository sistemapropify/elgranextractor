"""Pruebas de la exportación a Excel de la tabla de propiedades scrapeadas."""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone

from ingestas.scraping_export import (
    CAMPOS_EXPORT,
    ENCABEZADOS_EXPORT,
    _normalizar_valor,
    construir_libro,
)


class _PropiedadFake:
    """Doble de prueba de PropiedadesCompetencia (sin base de datos)."""

    def __init__(self, **valores):
        self.__dict__.update(valores)

    def get_estado_publicacion_display(self):
        return 'Activa'

    def get_tipo_inmueble_display(self):
        return 'Casa'

    def get_tipo_operacion_display(self):
        return 'Venta'

    def get_precision_ubicacion_display(self):
        return 'Exacta'


class NormalizarValorTests(SimpleTestCase):
    def test_none_se_exporta_vacio(self):
        self.assertEqual(_normalizar_valor(None), '')

    def test_decimal_se_exporta_como_float(self):
        self.assertEqual(_normalizar_valor(Decimal('150000.50')), 150000.50)

    def test_fecha_se_exporta_como_datetime(self):
        self.assertEqual(_normalizar_valor(date(2026, 2, 10)), datetime(2026, 2, 10, 0, 0))

    def test_datetime_aware_se_convierte_a_local_sin_tz(self):
        valor = datetime(2026, 2, 10, 12, 30, tzinfo=dt_timezone.utc)
        resultado = _normalizar_valor(valor)
        self.assertIsNone(resultado.tzinfo)
        esperado = timezone.localtime(valor).replace(tzinfo=None, microsecond=0)
        self.assertEqual(resultado, esperado)

    def test_json_se_serializa(self):
        self.assertEqual(_normalizar_valor({'a': 1}), '{"a": 1}')


class ConstruirLibroTests(SimpleTestCase):
    def setUp(self):
        self.propiedad = _PropiedadFake(
            id=7,
            fuente='properati',
            id_origen='ABC-123',
            estado_publicacion='activa',
            tipo_inmueble='Casa',
            tipo_operacion='Venta',
            titulo='Casa en Cayma',
            precio_usd=Decimal('120000.00'),
            precio_soles=None,
            area_m2=Decimal('180.50'),
            dormitorios=3,
            banos=2,
            estacionamientos=1,
            distrito='Cayma',
            provincia='Arequipa',
            departamento='Arequipa',
            direccion_texto='Av. Ejemplo 123',
            latitud=Decimal('-16.1234567'),
            longitud=Decimal('-71.5432100'),
            precision_ubicacion='exacta',
            antiguedad_anios=5,
            agencia_agente='Inmobiliaria X',
            descripcion='Linda casa',
            amenities='Piscina, Jardín',
            url='https://example.com/p/1',
            imagen_url='https://cdn.example.com/1.jpg',
            fecha_extraccion=timezone.now(),
            primera_vez_vista=timezone.now(),
            ultima_vez_vista=timezone.now(),
            fecha_primera_ausencia=None,
            fecha_retiro_confirmado=None,
            ausencias_consecutivas=0,
            creado_en=timezone.now(),
            actualizado_en=timezone.now(),
            datos_crudos={'id': 'ABC-123'},
        )

    def test_encabezados_coinciden_con_las_columnas_exportadas(self):
        libro, total = construir_libro([self.propiedad])
        self.assertEqual(total, 1)
        hoja = libro['Propiedades']
        encabezados = [celda.value for celda in hoja[1]]
        self.assertEqual(encabezados, [ENCABEZADOS_EXPORT[c] for c in CAMPOS_EXPORT])

    def test_valores_de_la_fila(self):
        libro, _ = construir_libro([self.propiedad])
        hoja = libro['Propiedades']
        valores = dict(zip(CAMPOS_EXPORT, [celda.value for celda in hoja[2]]))
        self.assertEqual(valores['fuente'], 'properati')
        self.assertEqual(valores['precio_usd'], 120000.0)
        self.assertEqual(valores['precio_soles'], '')
        self.assertEqual(valores['estado_publicacion'], 'Activa')
        self.assertEqual(valores['precision_ubicacion'], 'Exacta')
        self.assertEqual(valores['latitud'], -16.1234567)
        self.assertTrue(hoja.freeze_panes == 'A2')

    def test_hoja_de_datos_crudos_es_opcional(self):
        libro, _ = construir_libro([self.propiedad], incluir_crudos=True)
        self.assertIn('Datos crudos', libro.sheetnames)
        hoja_crudos = libro['Datos crudos']
        self.assertEqual(hoja_crudos['A2'].value, 7)
        self.assertEqual(hoja_crudos['D2'].value, '{"id": "ABC-123"}')

        libro_sin_crudos, _ = construir_libro([self.propiedad])
        self.assertNotIn('Datos crudos', libro_sin_crudos.sheetnames)

    def test_libro_vacio_tiene_solo_encabezados(self):
        libro, total = construir_libro([])
        hoja = libro['Propiedades']
        self.assertEqual(total, 0)
        self.assertEqual(hoja.max_row, 1)
