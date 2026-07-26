from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from intelligence.learning.auditor import audit_interaction
from intelligence.services.chat_processor import ChatProcessor
from intelligence.skills.cache import SkillCache
from intelligence.skills.propiedades.skill import BusquedaPropiedadesSkill


class LatencyOptimizationTests(SimpleTestCase):
    def test_cache_without_redis_url_does_not_attempt_connection(self):
        with patch.object(
            SkillCache,
            '_init_redis',
            side_effect=AssertionError('Redis should not be initialized'),
        ):
            cache = SkillCache(redis_url=None)

        self.assertFalse(cache._redis_available)

    def test_large_property_inventory_uses_concise_text(self):
        items = [
            {'field_values': {'title': f'Propiedad {index}'}}
            for index in range(89)
        ]

        response = ChatProcessor._format_grounded_property_items(items)

        self.assertIn('89 propiedades', response)
        self.assertIn('panel de resultados', response)
        self.assertNotIn('Propiedad 88', response)

    def test_structured_property_query_skips_embedding_inventory_load(self):
        skill = BusquedaPropiedadesSkill()
        params = {
            'semantic_query': (
                'mi cliente desea buscar terrenos de menos de 500 metros'
            ),
        }

        with (
            patch.object(skill, '_obtener_colecciones', return_value=[object()]),
            patch.object(skill, '_filtrar_por_sql', return_value=[]),
            patch(
                'intelligence.skills.propiedades.skill.'
                'IntelligenceDocument.objects.filter',
                side_effect=AssertionError(
                    'Structured search should not load all embeddings'
                ),
            ),
        ):
            result = skill.execute(params, context={'user_level': 1})

        self.assertTrue(result.success)
        self.assertEqual(result.data, [])
        self.assertEqual(params['semantic_query'], '')

    @override_settings(
        LEARNING_AI_AUDIT_ALL=True,
        LEARNING_AI_AUDIT_EVIDENCE_LIMIT=2,
    )
    @patch(
        'intelligence.services.llm.LLMService._call_deepseek_api',
        return_value=(False, '', None),
    )
    def test_ai_auditor_receives_bounded_evidence_sample(self, llm_call):
        evidence = [
            {'id': index, 'property_type': 'Terreno'}
            for index in range(10)
        ]

        audit_interaction(
            query='muestrame terrenos',
            response='Encontré 10 propiedades',
            orchestration_mode='agent_graph',
            result_count=10,
            grounded=True,
            execution_summary=[],
            result_evidence=evidence,
        )

        prompt = llm_call.call_args.kwargs['messages'][0]['content']
        self.assertIn('"result_evidence_total": 10', prompt)
        self.assertIn('"result_evidence_sampled": true', prompt)
        self.assertNotIn('"id": 9', prompt)
