from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from intelligence.skills.orchestrator import SkillOrchestrator
from intelligence.skills.propiedades.skill import BusquedaPropiedadesSkill


class PropertyIntentTests(SimpleTestCase):
    def test_extracts_bedrooms_deterministically(self):
        filters = BusquedaPropiedadesSkill()._analizar_intencion(
            'Qué departamentos tienes con 3 habitaciones en Cayma'
        )

        self.assertEqual(filters['distrito'], 'Cayma')
        self.assertEqual(filters['tipo_propiedad'], 'Departamento')
        self.assertEqual(filters['habitaciones'], 3)


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
