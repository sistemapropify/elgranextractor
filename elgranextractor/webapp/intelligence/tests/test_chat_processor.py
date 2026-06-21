import unittest
from unittest.mock import Mock, patch

from intelligence.services.chat_processor import ChatProcessor, ChatContext
from intelligence.skills.base import SkillResult
from intelligence.skills.orchestrator import SkillPipelineResult


class TestChatProcessorSkillInference(unittest.TestCase):
    def setUp(self):
        self.user = Mock()
        self.user.id = 1
        self.user.role = Mock(capabilities={})

        self.conversation = Mock()
        self.conversation.session_id = 'session-123'
        self.conversation.id = 123
        self.conversation.messages = []

    def test_infer_skill_request_with_price_query(self):
        ctx = ChatContext(
            user=self.user,
            message='Precio promedio de casas en Cayma',
            conversation=self.conversation,
            collections=['propiedades'],
        )

        intent = Mock()
        intent.intent = Mock(value='consulta_precio')
        intent.extracted_params = {
            'zonas': ['cayma'],
            'tipos_propiedad': ['casa'],
        }

        with patch(
            'intelligence.services.chat_processor.SKILL_SYSTEM.registry.search_skills'
        ) as mock_search, patch(
            'intelligence.services.chat_processor.ChatProcessor._fetch_price_records'
        ) as mock_fetch, patch(
            'intelligence.services.chat_processor.ChatProcessor._save_response'
        ) as mock_save, patch(
            'intelligence.services.chat_processor.ChatProcessor._save_post_process'
        ) as mock_post, patch(
            'intelligence.services.chat_processor.SKILL_SYSTEM.execute_skill'
        ) as mock_execute:
            mock_search.return_value = [
                {
                    'name': 'reporte_precios_zona',
                    'description': 'Genera un reporte de precios promedio y tendencias para una zona y tipo de propiedad',
                }
            ]
            mock_fetch.return_value = [
                {'zona': 'Cayma', 'tipo_propiedad': 'Casa', 'precio': 200000},
            ]
            mock_save.return_value = 'message-1'
            mock_post.return_value = None
            mock_execute.return_value = SkillResult.ok(data={'reporte': 'OK'})

            result = ChatProcessor._infer_skill_request(ctx, intent, 'trace-1')

        self.assertTrue(result.success)
        self.assertEqual(result.metadata['skill_name'], 'reporte_precios_zona')
        self.assertEqual(ctx.skill_name, 'reporte_precios_zona')
        self.assertEqual(ctx.skill_params['zona'], 'cayma')
        self.assertEqual(ctx.skill_params['tipo_propiedad'], 'casa')
        self.assertEqual(ctx.skill_params['registros'][0]['precio'], 200000)

    def test_infer_math_skill_request(self):
        ctx = ChatContext(
            user=self.user,
            message='Cuánto es 3 por 5',
            conversation=self.conversation,
            collections=['propiedades'],
        )

        intent = Mock()
        intent.intent = Mock(value='general')
        intent.extracted_params = {}

        with patch(
            'intelligence.services.chat_processor.SKILL_SYSTEM.registry.search_skills'
        ) as mock_search, patch(
            'intelligence.services.chat_processor.ChatProcessor._process_skill_request'
        ) as mock_process:
            mock_search.return_value = [
                {
                    'name': 'multiplicacion',
                    'description': 'Multiplica dos números.',
                }
            ]
            mock_process.return_value = SkillResult.ok(data={'resultado': 15})

            result = ChatProcessor._infer_skill_request(ctx, intent, 'trace-2')

        self.assertTrue(result.success)
        self.assertEqual(ctx.skill_name, 'multiplicacion')
        self.assertEqual(ctx.skill_params, {'a': 3.0, 'b': 5.0})

    def test_process_skill_pipeline_request(self):
        ctx = ChatContext(
            user=self.user,
            message='Ejecutar pipeline de skills',
            conversation=self.conversation,
            skill_pipeline=[
                {'name': 'suma', 'parameters': {'a': 2, 'b': 3}},
                {'name': 'suma', 'parameters': {'a': 5, 'b': 7}},
            ],
            skill_pipeline_mode='parallel',
        )

        with patch(
            'intelligence.services.chat_processor.SKILL_SYSTEM.execute_skill_pipeline'
        ) as mock_execute_pipeline, patch(
            'intelligence.services.chat_processor.ChatProcessor._save_response'
        ) as mock_save, patch(
            'intelligence.services.chat_processor.ChatProcessor._save_post_process'
        ) as mock_post:
            mock_execute_pipeline.return_value = SkillPipelineResult(
                success=True,
                steps=[
                    {'name': 'suma', 'success': True, 'result_data': {'resultado': 5}},
                    {'name': 'suma', 'success': True, 'result_data': {'resultado': 12}},
                ],
                data={'suma': {'resultado': 12}},
            )
            mock_save.return_value = 'message-1'
            mock_post.return_value = None

            result = ChatProcessor._process_skill_pipeline_request(ctx, 'trace-1')

        self.assertTrue(result.success)
        self.assertEqual(result.metadata['skill_pipeline_mode'], 'parallel')
        self.assertIn('pipeline_result', result.metadata)
        self.assertEqual(result.metadata['pipeline_result']['suma']['resultado'], 12)
        self.assertEqual(result.response_text.count('suma:'), 2)

    def test_build_skill_params_for_price_query_from_rag_results(self):
        ctx = ChatContext(
            user=self.user,
            message='Precio promedio de casas en Cayma',
            conversation=self.conversation,
            collections=['propiedades'],
        )

        intent = Mock()
        intent.extracted_params = {
            'zonas': ['cayma'],
            'tipos_propiedad': ['casa'],
        }

        with patch('intelligence.services.chat_processor.RAGService.search_dynamic') as mock_rag:
            mock_rag.return_value = [
                {'field_values': {'price': '250000', 'zona': 'Cayma', 'property_type': 'Casa'}},
                {'field_values': {'price': '270000', 'zona': 'Cayma', 'property_type': 'Casa'}},
            ]

            params = ChatProcessor._build_skill_params_for_price_query(ctx, intent)

        self.assertEqual(params['zona'], 'cayma')
        self.assertEqual(params['tipo_propiedad'], 'casa')
        self.assertEqual(len(params['registros']), 2)


if __name__ == '__main__':
    unittest.main()
