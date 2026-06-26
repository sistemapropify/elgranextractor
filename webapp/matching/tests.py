"""
Tests unitarios para el sistema de matching v4.

Cubre:
- Filtros duros (10 discriminadores)
- Scoring blando (8 factores)
- Scoring semántico (función escalonada)
- Filtrado final (umbral 70%, top-10, ranking)
- Casos de borde
"""

from decimal import Decimal
from django.test import TestCase

from . import scoring


class TestFiltrosDuros(TestCase):
    """Pruebas para los 10 filtros duros (FASE 1)."""

    def setUp(self):
        self.req_data = {
            'condicion': 'compra',
            'tipo_propiedad': 'departamento',
            'forma_pago': 'credito_hipotecario',
            'presupuesto_monto': 200000.0,
            'presupuesto_moneda': 'PEN',
            'habitaciones': 3,
            'banos': 2,
            'area_m2': 100.0,
            'ascensor': 'si',
            'cochera': 'si',
            'distritos_lista': ['miraflores', 'san isidro'],
            'distrito_obligatorio': True,
            'antiguedad_max': 10,
        }

        self.prop_base = {
            'operation_type_id': 1,  # compra
            'property_type_id': 3,   # departamento
            'price': 190000.0,
            'currency_id': 2,        # PEN
            'bedrooms': 3,
            'bathrooms': 2,
            'built_area': 100.0,
            'has_elevator': True,
            'garage_spaces': 2,
            'district_id': '1',
            'district_name': 'Miraflores',
            'antiquity_years': 5,
        }

    # ── Filtro 1: Condición ─────────────────────────────────────

    def test_filtro_condicion_pasa(self):
        """Propiedad con misma condición debe pasar."""
        prop = dict(self.prop_base)
        prop['operation_type_id'] = 1  # compra
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de condición")

    def test_filtro_condicion_falla(self):
        """Propiedad con condición diferente debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['operation_type_id'] = 2  # alquiler
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'condicion',
                         "Debería fallar por condición diferente")

    # ── Filtro 2: Tipo de propiedad ─────────────────────────────

    def test_filtro_tipo_pasa(self):
        """Propiedad con mismo tipo debe pasar."""
        prop = dict(self.prop_base)
        prop['property_type_id'] = 3  # departamento
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de tipo")

    def test_filtro_tipo_falla(self):
        """Propiedad con tipo diferente debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['property_type_id'] = 1  # casa
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'tipo_propiedad',
                         "Debería fallar por tipo diferente")

    # ── Filtro 3: Forma de pago ─────────────────────────────────

    def test_filtro_forma_pago_pasa_credito(self):
        """Propiedad que acepta crédito debe pasar."""
        prop = dict(self.prop_base)
        prop['forma_pago'] = 'credito_hipotecario'
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de forma de pago")

    def test_filtro_forma_pago_falla_solo_efectivo(self):
        """Propiedad solo_efectivo con req credito debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['forma_pago'] = 'solo_efectivo'
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'forma_pago',
                         "Debería fallar por forma de pago solo_efectivo")

    # ── Filtro 4: Presupuesto máximo ────────────────────────────

    def test_filtro_presupuesto_max_pasa(self):
        """Propiedad dentro del presupuesto debe pasar."""
        prop = dict(self.prop_base)
        prop['price'] = 200000.0
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de presupuesto máximo")

    def test_filtro_presupuesto_max_falla(self):
        """Propiedad muy cara debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['price'] = 220000.0  # > 200k * 1.05 = 210k
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'presupuesto_maximo',
                         "Debería fallar por exceder presupuesto máximo")

    # ── Filtro 5: Presupuesto mínimo ────────────────────────────

    def test_filtro_presupuesto_min_pasa(self):
        """Propiedad dentro del rango mínimo debe pasar."""
        prop = dict(self.prop_base)
        prop['price'] = 120000.0  # > 200k * 0.50 = 100k
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de presupuesto mínimo")

    def test_filtro_presupuesto_min_falla(self):
        """Propiedad muy barata debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['price'] = 80000.0  # < 200k * 0.50 = 100k
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'presupuesto_minimo',
                         "Debería fallar por estar bajo presupuesto mínimo")

    # ── Filtro 6: Ascensor ──────────────────────────────────────

    def test_filtro_ascensor_pasa(self):
        """Propiedad con ascensor debe pasar."""
        prop = dict(self.prop_base)
        prop['has_elevator'] = True
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de ascensor")

    def test_filtro_ascensor_falla(self):
        """Propiedad sin ascensor con req 'si' debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['has_elevator'] = False
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'ascensor',
                         "Debería fallar por falta de ascensor")

    # ── Filtro 7: Cocheras ──────────────────────────────────────

    def test_filtro_cocheras_pasa(self):
        """Propiedad con cocheras suficientes debe pasar."""
        prop = dict(self.prop_base)
        prop['garage_spaces'] = 2
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de cocheras")

    def test_filtro_cocheras_falla(self):
        """Propiedad sin cocheras debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['garage_spaces'] = 0
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'cocheras',
                         "Debería fallar por falta de cocheras")

    # ── Filtro 8: Habitaciones mínimas ──────────────────────────

    def test_filtro_habitaciones_pasa(self):
        """Propiedad con habitaciones suficientes debe pasar."""
        prop = dict(self.prop_base)
        prop['bedrooms'] = 3
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de habitaciones")

    def test_filtro_habitaciones_falla(self):
        """Propiedad con menos habitaciones debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['bedrooms'] = 2
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'habitaciones',
                         "Debería fallar por falta de habitaciones")

    # ── Filtro 9: Baños mínimos ─────────────────────────────────

    def test_filtro_banos_pasa(self):
        """Propiedad con baños suficientes debe pasar."""
        prop = dict(self.prop_base)
        prop['bathrooms'] = 2
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de baños")

    def test_filtro_banos_falla(self):
        """Propiedad con menos baños debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['bathrooms'] = 1
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'banos',
                         "Debería fallar por falta de baños")

    # ── Filtro 10: Distrito obligatorio ─────────────────────────

    def test_filtro_distrito_pasa(self):
        """Propiedad en distrito preferido debe pasar."""
        prop = dict(self.prop_base)
        prop['district_name'] = 'Miraflores'
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertIsNone(resultado, "Debería pasar filtro de distrito")

    def test_filtro_distrito_falla(self):
        """Propiedad fuera de distritos preferidos debe ser eliminada."""
        prop = dict(self.prop_base)
        prop['district_name'] = 'Comas'
        resultado = scoring.aplicar_filtros_duros(prop, self.req_data)
        self.assertEqual(resultado, 'distrito',
                         "Debería fallar por distrito no preferido")


class TestScoringBlando(TestCase):
    """Pruebas para los 8 factores de scoring blando (FASE 2)."""

    def setUp(self):
        self.req_data = {
            'condicion': 'compra',
            'tipo_propiedad': 'departamento',
            'presupuesto_monto': 200000.0,
            'presupuesto_moneda': 'PEN',
            'habitaciones': 3,
            'banos': 2,
            'area_m2': 100.0,
            'ascensor': 'si',
            'cochera': 'si',
            'distritos_lista': ['miraflores', 'san isidro'],
            'caracteristicas_extra': 'piscina gimnasio',
            'antiguedad_max': 10,
        }

        self.prop_base = {
            'price': 200000.0,
            'currency_id': 2,  # PEN
            'bedrooms': 3,
            'bathrooms': 2,
            'built_area': 100.0,
            'has_pool': True,
            'has_garden': False,
            'has_bbq': False,
            'has_terrace': False,
            'has_security': False,
            'pet_friendly': False,
            'garage_spaces': 2,
            'antiquity_years': 5,
            'district_name': 'Miraflores',
        }

    # ── Factor 1: Distrito ──────────────────────────────────────

    def test_score_distrito_max(self):
        """Primer distrito preferido debe dar score máximo (15)."""
        prop = dict(self.prop_base)
        prop['district_name'] = 'Miraflores'
        score = scoring._score_distrito(prop, self.req_data)
        self.assertAlmostEqual(score, 15.0, places=2,
                               msg="Primer distrito debe dar score=15")

    def test_score_distrito_segundo(self):
        """Segundo distrito preferido debe dar score=13.5."""
        prop = dict(self.prop_base)
        prop['district_name'] = 'San Isidro'
        score = scoring._score_distrito(prop, self.req_data)
        self.assertAlmostEqual(score, 13.5, places=2,
                               msg="Segundo distrito debe dar score=13.5")

    def test_score_distrito_fuera(self):
        """Distrito no preferido debe dar score=0."""
        prop = dict(self.prop_base)
        prop['district_name'] = 'Comas'
        score = scoring._score_distrito(prop, self.req_data)
        self.assertAlmostEqual(score, 0.0, places=2,
                               msg="Distrito no preferido debe dar score=0")

    # ── Factor 2: Precio (gaussiana) ────────────────────────────

    def test_score_precio_exacto(self):
        """Precio exactamente igual al presupuesto debe dar score=20."""
        score = scoring._score_precio(self.prop_base, self.req_data)
        self.assertAlmostEqual(score, 20.0, places=2,
                               msg="Precio exacto debe dar score=20")

    def test_score_precio_5pct(self):
        """Precio con 5% de diferencia debe dar ~17.64."""
        prop = dict(self.prop_base)
        prop['price'] = 190000.0
        score = scoring._score_precio(prop, self.req_data)
        self.assertAlmostEqual(score, 17.64, places=1,
                               msg="Precio 5% abajo debe dar ~17.64")

    def test_score_precio_muy_barato(self):
        """Precio 60% menor debe dar ~0."""
        prop = dict(self.prop_base)
        prop['price'] = 80000.0
        score = scoring._score_precio(prop, self.req_data)
        self.assertAlmostEqual(score, 0.0, places=1,
                               msg="Precio 60% menor debe dar ~0")

    # ── Factor 3: Habitaciones (distancia) ─────────────────────

    def test_score_habitaciones_exactas(self):
        """Mismas habitaciones debe dar score=15."""
        score = scoring._score_habitaciones(self.prop_base, self.req_data)
        self.assertAlmostEqual(score, 15.0, places=2,
                               msg="Habitaciones exactas debe dar score=15")

    def test_score_habitaciones_extra(self):
        """2 habitaciones extra debe dar score=12."""
        prop = dict(self.prop_base)
        prop['bedrooms'] = 5
        score = scoring._score_habitaciones(prop, self.req_data)
        self.assertAlmostEqual(score, 12.0, places=2,
                               msg="2 habitaciones extra debe dar score=12")

    # ── Factor 4: Baños (distancia) ────────────────────────────

    def test_score_banos_exactos(self):
        """Mismos baños debe dar score=10."""
        score = scoring._score_banos(self.prop_base, self.req_data)
        self.assertAlmostEqual(score, 10.0, places=2,
                               msg="Baños exactos debe dar score=10")

    def test_score_banos_extra(self):
        """1 baño extra debe dar score=8.5."""
        prop = dict(self.prop_base)
        prop['bathrooms'] = 3
        score = scoring._score_banos(prop, self.req_data)
        self.assertAlmostEqual(score, 8.5, places=2,
                               msg="1 baño extra debe dar score=8.5")

    # ── Factor 5: Área (distancia) ─────────────────────────────

    def test_score_area_exacta(self):
        """Misma área debe dar score=10."""
        score = scoring._score_area(self.prop_base, self.req_data)
        self.assertAlmostEqual(score, 10.0, places=2,
                               msg="Área exacta debe dar score=10")

    def test_score_area_20pct(self):
        """20% más área debe dar score=9."""
        prop = dict(self.prop_base)
        prop['built_area'] = 120.0
        score = scoring._score_area(prop, self.req_data)
        self.assertAlmostEqual(score, 9.0, places=2,
                               msg="20% más área debe dar score=9")

    # ── Factor 6: Amenities (Jaccard) ──────────────────────────

    def test_score_amenities_todas(self):
        """Todos los amenities coinciden debe dar score=10."""
        score = scoring._score_amenities(self.prop_base, self.req_data)
        self.assertAlmostEqual(score, 10.0, places=2,
                               msg="Todos los amenities deben dar score=10")

    def test_score_amenities_ninguna(self):
        """Sin amenities en req debe dar score neutro (5)."""
        req_data = dict(self.req_data)
        req_data['caracteristicas_extra'] = ''
        score = scoring._score_amenities(self.prop_base, req_data)
        self.assertAlmostEqual(score, 5.0, places=2,
                               msg="Sin amenities debe dar score neutro=5")

    # ── Factor 7: Antigüedad (distancia) ───────────────────────

    def test_score_antiguedad_maxima(self):
        """Antigüedad igual a la máxima debe dar score=5."""
        score = scoring._score_antiguedad(self.prop_base, self.req_data)
        self.assertAlmostEqual(score, 2.5, places=2,
                               msg="5 años de 10 máx debe dar score=2.5")

    def test_score_antiguedad_sin_max(self):
        """Sin antigüedad máxima debe dar score neutro (2.5)."""
        req_data = dict(self.req_data)
        del req_data['antiguedad_max']
        score = scoring._score_antiguedad(self.prop_base, req_data)
        self.assertAlmostEqual(score, 2.5, places=2,
                               msg="Sin antigüedad máxima debe dar score=2.5")

    # ── Factor 8: Semántico (escalonada) ───────────────────────

    def test_score_semantico_excelente(self):
        """Similarity >= 0.85 debe dar score=15."""
        score = scoring._score_semantico(0.90)
        self.assertAlmostEqual(score, 15.0, places=2,
                               msg="Similarity 0.90 debe dar score=15")

    def test_score_semantico_bueno(self):
        """Similarity >= 0.70 debe dar score=12."""
        score = scoring._score_semantico(0.75)
        self.assertAlmostEqual(score, 12.0, places=2,
                               msg="Similarity 0.75 debe dar score=12")

    def test_score_semantico_aceptable(self):
        """Similarity >= 0.55 debe dar score=9."""
        score = scoring._score_semantico(0.60)
        self.assertAlmostEqual(score, 9.0, places=2,
                               msg="Similarity 0.60 debe dar score=9")

    def test_score_semantico_debil(self):
        """Similarity >= 0.40 debe dar score=4.5."""
        score = scoring._score_semantico(0.45)
        self.assertAlmostEqual(score, 4.5, places=2,
                               msg="Similarity 0.45 debe dar score=4.5")

    def test_score_semantico_muy_debil(self):
        """Similarity < 0.40 debe dar score=0."""
        score = scoring._score_semantico(0.30)
        self.assertAlmostEqual(score, 0.0, places=2,
                               msg="Similarity 0.30 debe dar score=0")

    def test_score_semantico_sin_faiss(self):
        """Sin FAISS disponible debe dar score neutro (7.5)."""
        score = scoring._score_semantico(None)
        self.assertAlmostEqual(score, 7.5, places=2,
                               msg="Sin FAISS debe dar score neutro=7.5")

    # ── Test integral: score total ─────────────────────────────

    def test_score_total_completo(self):
        """Score total debe ser suma de todos los factores."""
        score_total, score_detalle = scoring.calcular_scoring_total(
            self.prop_base, self.req_data
        )
        # Verificar que score_detalle tenga los 8 factores
        factores_esperados = {'distrito', 'precio', 'habitaciones', 'banos',
                              'area', 'amenities', 'antiguedad', 'semantico'}
        self.assertEqual(set(score_detalle.keys()), factores_esperados,
                         "Score detalle debe tener los 8 factores")
        # Verificar que cada factor tenga score, peso_maximo, detalle
        for factor, data in score_detalle.items():
            self.assertIn('score', data,
                          f"Factor {factor} debe tener 'score'")
            self.assertIn('peso_maximo', data,
                          f"Factor {factor} debe tener 'peso_maximo'")
            self.assertIn('detalle', data,
                          f"Factor {factor} debe tener 'detalle'")
        # Score total debe ser > 0 y <= 100
        self.assertGreater(score_total, 0,
                           "Score total debe ser > 0")
        self.assertLessEqual(score_total, 100,
                             "Score total debe ser <= 100")


class TestFiltradoFinal(TestCase):
    """Pruebas para el filtrado final (FASE 3)."""

    def setUp(self):
        self.resultados = [
            {'score_total': 85.0, 'propiedad_id': 1},
            {'score_total': 92.0, 'propiedad_id': 2},
            {'score_total': 65.0, 'propiedad_id': 3},
            {'score_total': 78.0, 'propiedad_id': 4},
            {'score_total': 95.0, 'propiedad_id': 5},
            {'score_total': 55.0, 'propiedad_id': 6},
            {'score_total': 88.0, 'propiedad_id': 7},
            {'score_total': 72.0, 'propiedad_id': 8},
            {'score_total': 45.0, 'propiedad_id': 9},
            {'score_total': 90.0, 'propiedad_id': 10},
            {'score_total': 81.0, 'propiedad_id': 11},
            {'score_total': 73.0, 'propiedad_id': 12},
        ]

    def test_umbral_minimo(self):
        """Matches con score < 70 deben ser descartados."""
        filtrados = scoring.filtrar_resultados_finales(
            self.resultados, umbral_minimo=70, top_k=10
        )
        for r in filtrados:
            self.assertGreaterEqual(r['score_total'], 70,
                                    "Todos los matches deben tener score >= 70")

    def test_top_k_limit(self):
        """Solo deben retornarse top 10 matches."""
        filtrados = scoring.filtrar_resultados_finales(
            self.resultados, umbral_minimo=0, top_k=10
        )
        self.assertLessEqual(len(filtrados), 10,
                             "No debe haber más de 10 matches")

    def test_ranking_asignado(self):
        """El ranking debe asignarse correctamente (1 = mejor score)."""
        filtrados = scoring.filtrar_resultados_finales(
            self.resultados, umbral_minimo=0, top_k=10
        )
        for i, r in enumerate(filtrados, 1):
            self.assertEqual(r['ranking'], i,
                             f"Ranking debe ser {i} para match en posición {i}")

    def test_orden_descendente(self):
        """Los resultados deben estar ordenados por score descendente."""
        filtrados = scoring.filtrar_resultados_finales(
            self.resultados, umbral_minimo=0, top_k=10
        )
        scores = [r['score_total'] for r in filtrados]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "Los scores deben estar en orden descendente")


class TestCasosBorde(TestCase):
    """Pruebas para casos borde del sistema de matching."""

    def test_requerimiento_sin_amenities(self):
        """Requerimiento sin amenities debe dar score neutro."""
        req_data = {
            'presupuesto_monto': 200000.0,
            'presupuesto_moneda': 'PEN',
            'distritos_lista': ['miraflores'],
            'caracteristicas_extra': '',
        }
        prop = {
            'price': 200000.0,
            'currency_id': 2,
            'has_pool': True,
            'has_garden': True,
            'district_name': 'Miraflores',
        }
        score = scoring._score_amenities(prop, req_data)
        self.assertAlmostEqual(score, 5.0, places=2,
                               msg="Sin amenities en req debe dar score neutro")

    def test_propiedad_sin_amenities(self):
        """Propiedad sin amenities debe dar score parcial."""
        req_data = {
            'presupuesto_monto': 200000.0,
            'presupuesto_moneda': 'PEN',
            'distritos_lista': ['miraflores'],
            'caracteristicas_extra': 'piscina gimnasio',
        }
        prop = {
            'price': 200000.0,
            'currency_id': 2,
            'has_pool': False,
            'has_garden': False,
            'district_name': 'Miraflores',
        }
        score = scoring._score_amenities(prop, req_data)
        self.assertEqual(score, 0.0,
                         "Propiedad sin amenities debe dar score=0")

    def test_requerimiento_sin_presupuesto(self):
        """Requerimiento sin presupuesto debe dar score neutro en precio."""
        req_data = {
            'presupuesto_monto': None,
            'presupuesto_moneda': 'PEN',
            'distritos_lista': ['miraflores'],
        }
        prop = {
            'price': 200000.0,
            'currency_id': 2,
            'district_name': 'Miraflores',
        }
        score = scoring._score_precio(prop, req_data)
        self.assertAlmostEqual(score, 10.0, places=2,
                               msg="Sin presupuesto debe dar score neutro=10")

    def test_scoring_total_sin_semantico(self):
        """Score total sin semántico debe funcionar con score neutro."""
        req_data = {
            'presupuesto_monto': 200000.0,
            'presupuesto_moneda': 'PEN',
            'distritos_lista': ['miraflores'],
            'habitaciones': 3,
            'banos': 2,
            'area_m2': 100.0,
            'caracteristicas_extra': '',
        }
        prop = {
            'price': 200000.0,
            'currency_id': 2,
            'bedrooms': 3,
            'bathrooms': 2,
            'built_area': 100.0,
            'district_name': 'Miraflores',
        }
        score_total, score_detalle = scoring.calcular_scoring_total(prop, req_data)
        # score_semantico debe ser 7.5 (neutro)
        self.assertAlmostEqual(
            score_detalle['semantico']['score'], 7.5, places=2,
            msg="Sin semántico debe dar score neutro=7.5"
        )

    def test_preparar_req_data_estructura(self):
        """preparar_req_data debe retornar dict con estructura correcta."""
        # Simulamos un objeto requerimiento
        class MockRequerimiento:
            id = 1
            condicion = 'compra'
            tipo_propiedad = 'departamento'
            distritos = 'Miraflores, San Isidro'
            presupuesto_monto = Decimal('200000.00')
            presupuesto_moneda = 'PEN'
            presupuesto_forma_pago = 'credito_hipotecario'
            habitaciones = 3
            banos = 2
            area_m2 = Decimal('100.00')
            ascensor = 'si'
            cochera = 'si'
            caracteristicas_extra = 'piscina gimnasio'
            distritos_lista = ['Miraflores', 'San Isidro']

        req_data = scoring.preparar_req_data(MockRequerimiento())
        campos_esperados = [
            'id', 'condicion', 'tipo_propiedad', 'distritos',
            'distritos_lista', 'distrito_obligatorio',
            'presupuesto_monto', 'presupuesto_moneda',
            'forma_pago', 'habitaciones', 'banos', 'area_m2',
            'ascensor', 'cochera', 'caracteristicas_extra',
        ]
        for campo in campos_esperados:
            self.assertIn(campo, req_data,
                          f"preparar_req_data debe incluir '{campo}'")
