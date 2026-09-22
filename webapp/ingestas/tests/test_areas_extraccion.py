"""Extracción de área de terreno y área construida (``scrapi.areas``).

Un anuncio puede traer las dos superficies a la vez (típico en casas) o solo la
del terreno (lotes). Antes se colapsaban en un único ``area_m2`` y se perdía una.
"""

from django.test import SimpleTestCase

from scrapi.areas import (
    area_desde_medidas,
    calcular_area_m2,
    calcular_areas,
    extraer_areas_de_texto,
    parsear_area,
)
from scrapi.normalization import validate_row

DESCRIPCION_CASA = """
𝗩𝗘𝗡𝗧𝗔 𝗖𝗔𝗦𝗔 𝗠𝗢𝗗𝗘𝗥𝗡𝗔 𝗘𝗡 𝗖𝗔𝗟𝗟𝗘 𝗟𝗢𝗦 𝗔𝗥𝗖𝗘𝗦 - 𝗖𝗔𝗬𝗠𝗔
Vendo moderna casa de 3 niveles, cálida y bien iluminada en residencial privada.
🏡 ÁREA DE TERRENO: 120 m2
🏡 ÁREA CONSTRUIDA: 185 m2
💰 PRECIO: $460,000 Dólares
"""

DESCRIPCION_TERRENO = 'Lote en venta en Cayma. Terreno: 200 m2, con servicios básicos.'

URBANIA_CARACTERISTICAS = '128 m2 totales, 90 m2 construidos, 3 dorm, 2 baños'


class ParseoAreaTests(SimpleTestCase):
    """Normalización de un valor crudo a m²."""

    def test_numeros_y_unidades(self):
        self.assertEqual(parsear_area('120'), 120.0)
        self.assertEqual(parsear_area('185 m²'), 185.0)
        self.assertEqual(parsear_area('120 m2'), 120.0)
        self.assertEqual(parsear_area(150), 150.0)

    def test_miles_y_decimales(self):
        self.assertEqual(parsear_area('1.200,50'), 1200.5)
        self.assertEqual(parsear_area('1,200.50'), 1200.5)
        self.assertEqual(parsear_area('120,5'), 120.5)

    def test_sin_dato_o_cero_es_none(self):
        self.assertIsNone(parsear_area('0'))
        self.assertIsNone(parsear_area('sin dato'))
        self.assertIsNone(parsear_area(''))
        self.assertIsNone(parsear_area(None))

    def test_medidas_frente_por_fondo(self):
        self.assertEqual(area_desde_medidas('8.00 X 16.00'), 128.0)
        self.assertIsNone(area_desde_medidas('0.00 X 0.00'))
        self.assertIsNone(area_desde_medidas(''))


class TextoEtiquetadoTests(SimpleTestCase):
    """Lectura de las superficies escritas dentro de la descripción."""

    def test_casa_con_terreno_y_construida(self):
        self.assertEqual(
            extraer_areas_de_texto(DESCRIPCION_CASA),
            {'area_terreno': 120.0, 'area_construida': 185.0},
        )

    def test_terreno_solo_area_de_terreno(self):
        self.assertEqual(
            extraer_areas_de_texto(DESCRIPCION_TERRENO),
            {'area_terreno': 200.0, 'area_construida': None},
        )

    def test_sufijos_totales_y_construidos(self):
        self.assertEqual(
            extraer_areas_de_texto(URBANIA_CARACTERISTICAS),
            {'area_terreno': 128.0, 'area_construida': 90.0},
        )

    def test_sin_etiqueta_no_se_asume_construccion(self):
        self.assertEqual(
            extraer_areas_de_texto('Hermosa casa con 120 m2 y vista al parque'),
            {'area_terreno': None, 'area_construida': None},
        )


class AreasCalculoTests(SimpleTestCase):
    """Combina campos estructurados del portal con el texto."""

    def test_casa_desde_descripcion(self):
        self.assertEqual(
            calcular_areas({'description': DESCRIPCION_CASA}),
            {'area_terreno': 120.0, 'area_construida': 185.0, 'area_m2': 185.0},
        )

    def test_terreno_usa_area_de_terreno_como_principal(self):
        self.assertEqual(
            calcular_areas({'description': DESCRIPCION_TERRENO}),
            {'area_terreno': 200.0, 'area_construida': None, 'area_m2': 200.0},
        )

    def test_campos_estructurados_tienen_prioridad(self):
        self.assertEqual(
            calcular_areas({'Area Terreno': '120 m2', 'Area Construida': '185 m2'}),
            {'area_terreno': 120.0, 'area_construida': 185.0, 'area_m2': 185.0},
        )

    def test_adondevivir_area_total_y_area(self):
        self.assertEqual(
            calcular_areas({'area_total': '300 m2', 'area': '210 m2'}),
            {'area_terreno': 300.0, 'area_construida': 210.0, 'area_m2': 210.0},
        )

    def test_medidas_como_respaldo(self):
        self.assertEqual(calcular_area_m2({'Medidas': '10 X 20'}), 200.0)

    def test_propiedad_vacia(self):
        self.assertEqual(
            calcular_areas({}),
            {'area_terreno': None, 'area_construida': None, 'area_m2': None},
        )


class ValidacionTests(SimpleTestCase):
    """``validate_row`` debe conservar las dos superficies."""

    def test_conserva_ambas_areas(self):
        fila = validate_row({'id_origen': 'X1', 'area_m2': 185,
                             'area_terreno': 120, 'area_construida': 185})
        self.assertEqual(fila['area_terreno'], 120)
        self.assertEqual(fila['area_construida'], 185)

    def test_area_cero_o_negativa_se_anula(self):
        fila = validate_row({'id_origen': 'X1', 'area_terreno': 0, 'area_construida': -5})
        self.assertIsNone(fila['area_terreno'])
        self.assertIsNone(fila['area_construida'])
