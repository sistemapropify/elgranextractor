import os
from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.agents.semantic_execution_judge import SemanticExecutionJudge


class SemanticExecutionJudgeTests(SimpleTestCase):
    def setUp(self):
        self.mode_patch = patch.dict(
            os.environ, {'EXECUTION_JUDGE_MODE': 'shadow'}
        )
        self.mode_patch.start()

    def tearDown(self):
        self.mode_patch.stop()

    def test_skips_simple_query_approved_by_level_one(self):
        result = SemanticExecutionJudge.evaluate(
            message='Muéstrame terrenos en Cayma',
            results={},
            deterministic_evaluation={'verdict': 'pass'},
        )
        self.assertFalse(result['enabled'])
        self.assertEqual(result['status'], 'skipped')

    @patch(
        'intelligence.agents.semantic_execution_judge.'
        'LLMService._call_deepseek_api'
    )
    def test_records_shadow_verdict_without_authority(self, mock_call):
        mock_call.return_value = (
            True,
            'ok',
            {'content': '''{
                "verdict": "clarify",
                "confidence": 0.94,
                "reason": "Faltan criterios de área y ubicación.",
                "signals": ["MISSING_CRITERIA"],
                "missing_information": ["área", "distrito"],
                "suggested_action": "Solicitar criterios"
            }'''},
        )

        result = SemanticExecutionJudge.evaluate(
            message='Qué propiedad es ideal para una clínica',
            results={},
            deterministic_evaluation={'verdict': 'clarify'},
        )

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['verdict'], 'clarify')
        self.assertEqual(result['mode'], 'shadow')
        self.assertFalse(result['authority_applied'])
        self.assertFalse(result['disagrees_with_deterministic'])

    @patch(
        'intelligence.agents.semantic_execution_judge.'
        'LLMService._call_deepseek_api'
    )
    def test_records_disagreement(self, mock_call):
        mock_call.return_value = (
            True,
            'ok',
            {'content': '{"verdict":"pass","confidence":0.7,"reason":"Suficiente","signals":[]}'},
        )
        result = SemanticExecutionJudge.evaluate(
            message='Cuál es la mejor oportunidad',
            results={},
            deterministic_evaluation={'verdict': 'clarify'},
        )
        self.assertTrue(result['disagrees_with_deterministic'])
        self.assertFalse(result['authority_applied'])

    @patch(
        'intelligence.agents.semantic_execution_judge.'
        'LLMService._call_deepseek_api'
    )
    def test_invalid_json_fails_open_without_authority(self, mock_call):
        mock_call.return_value = (True, 'ok', {'content': 'no-json'})
        result = SemanticExecutionJudge.evaluate(
            message='Recomiéndame una propiedad',
            results={},
            deterministic_evaluation={'verdict': 'clarify'},
        )
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['authority_applied'])
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(mock_call.call_count, 2)

    @patch.dict(
        os.environ,
        {'EXECUTION_JUDGE_MODE': 'advisory'},
    )
    @patch(
        'intelligence.agents.semantic_execution_judge.'
        'LLMService._call_deepseek_api'
    )
    def test_advisory_evaluates_simple_queries(self, mock_call):
        mock_call.return_value = (
            True,
            'ok',
            {'content': '{"verdict":"pass","confidence":0.97,"reason":"Coincide","signals":[]}'},
        )

        result = SemanticExecutionJudge.evaluate(
            message='Departamentos de 3 habitaciones en Cayma',
            results={},
            deterministic_evaluation={'verdict': 'pass'},
        )

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['verdict'], 'pass')
        self.assertEqual(result['attempts'], 1)

    @patch(
        'intelligence.agents.semantic_execution_judge.'
        'LLMService._call_deepseek_api'
    )
    def test_repairs_invalid_first_response_once(self, mock_call):
        mock_call.side_effect = [
            (True, 'ok', {'content': 'veredicto pass sin json'}),
            (
                True,
                'ok',
                {'content': '{"verdict":"pass","confidence":0.93,"reason":"Válido","signals":[]}'},
            ),
        ]

        result = SemanticExecutionJudge.evaluate(
            message='Recomiéndame una propiedad',
            results={},
            deterministic_evaluation={'verdict': 'clarify'},
        )

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['attempts'], 2)
