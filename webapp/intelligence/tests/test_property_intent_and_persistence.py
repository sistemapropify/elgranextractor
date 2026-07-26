from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from intelligence.skills.orchestrator import SkillOrchestrator
from intelligence.skills.propiedades.skill import BusquedaPropiedadesSkill
from intelligence.search.normalizer import SearchPlanNormalizer


class PropertyIntentTests(SimpleTestCase):
    def test_extracts_bedrooms_deterministically(self):
        filters = BusquedaPropiedadesSkill()._analizar_intencion(
            'Qué departamentos tienes con 3 habitaciones en Cayma'
        )

        self.assertEqual(filters['distrito'], 'Cayma')
        self.assertEqual(filters['tipo_propiedad'], 'Departamento')
        self.assertEqual(filters['habitaciones'], 3)

    def test_distinguishes_exact_from_minimum_bedrooms(self):
        skill = BusquedaPropiedadesSkill()

        exact = skill._analizar_intencion('propiedades con 3 habitaciones')
        minimum = skill._analizar_intencion(
            'propiedades con al menos 3 habitaciones'
        )
        greater = skill._analizar_intencion(
            'propiedades con más de 3 habitaciones'
        )

        self.assertEqual(exact['habitaciones'], 3)
        self.assertNotIn('habitaciones_min', exact)
        self.assertEqual(minimum['habitaciones_min'], 3)
        self.assertNotIn('habitaciones', minimum)
        self.assertEqual(greater['habitaciones_min'], 4)

    def test_search_plan_preserves_bedroom_operator(self):
        exact = SearchPlanNormalizer.params_from_message(
            'propiedades con 3 habitaciones'
        )
        minimum = SearchPlanNormalizer.params_from_message(
            'propiedades con mínimo 3 habitaciones'
        )

        self.assertEqual(exact['habitaciones'], 3)
        self.assertEqual(minimum['habitaciones_min'], 3)


class SkillExecutionPersistenceTests(SimpleTestCase):
    def test_decimal_results_are_normalized_before_jsonfield_save(self):
        record = SimpleNamespace(
            status='pending',
            latency_ms=0,
            cached=False,
            result=None,
            error_message=None,
            save=Mock(),
        )

        SkillOrchestrator._finalize_execution(
            None,
            record,
            'success',
            result_data={'price': Decimal('199900.00')},
            latency_ms=25,
        )

        self.assertEqual(record.result, {'price': '199900.00'})
        record.save.assert_called_once()
