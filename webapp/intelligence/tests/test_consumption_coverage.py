import json
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from intelligence.procesos_ia import normalizar_proceso
from intelligence.services.llm import LLMService


class ConsumptionCoverageTests(SimpleTestCase):
    def test_quality_historical_and_new_calls_are_classified(self):
        for caller in ('ingestas', 'ingestas.calidad_ia'):
            self.assertEqual(normalizar_proceso(caller)[0], 'calidad_scraping')

    @patch('intelligence.services.llm.AIConsumptionLog.registrar_llamada')
    @patch('intelligence.services.llm.requests.post')
    def test_tools_count_usage_even_when_no_valid_tool_is_returned(self, post, log):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            'usage': {'prompt_tokens': 100, 'completion_tokens': 25, 'total_tokens': 125},
            'choices': [],
        }
        self.assertFalse(LLMService.call_with_tools('system', 'query', []).success)
        log.assert_called_once()
        self.assertEqual(log.call_args.kwargs['total_tokens'], 125)
        self.assertEqual(log.call_args.kwargs['caller_app'], 'intelligence.tools')

    @patch('intelligence.services.llm.AIConsumptionLog.registrar_llamada')
    @patch('intelligence.services.llm.requests.post', side_effect=requests.exceptions.Timeout)
    def test_tools_timeout_is_recorded(self, post, log):
        self.assertFalse(LLMService.call_with_tools('system', 'query', []).success)
        log.assert_called_once()
        self.assertFalse(log.call_args.kwargs['success'])

    @patch.object(LLMService, 'API_KEY', 'test-not-a-real-key')
    @patch('intelligence.services.llm.AIConsumptionLog.registrar_llamada')
    @patch('intelligence.services.llm.requests.post')
    def test_stream_records_final_usage_once(self, post, log):
        response = post.return_value
        response.status_code = 200
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hola"}}]}',
            b'data: {"choices":[],"usage":{"prompt_tokens":100,"completion_tokens":20,"total_tokens":120}}',
            b'data: [DONE]',
        ]
        chunks = list(LLMService.generate_streaming_response('hola'))
        self.assertEqual(json.loads(chunks[-1])['type'], 'complete')
        self.assertTrue(post.call_args.kwargs['json']['stream_options']['include_usage'])
        log.assert_called_once()
        self.assertEqual(log.call_args.kwargs['total_tokens'], 120)
        response.close.assert_called_once()

    @patch.object(LLMService, 'API_KEY', 'test-not-a-real-key')
    @patch('intelligence.services.llm.AIConsumptionLog.registrar_llamada')
    @patch('intelligence.services.llm.requests.post')
    def test_cancelled_stream_is_recorded_as_unknown_cost(self, post, log):
        post.return_value.status_code = 200
        post.return_value.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hola"}}]}',
        ]
        stream = LLMService.generate_streaming_response('hola')
        next(stream)
        stream.close()
        log.assert_called_once()
        self.assertFalse(log.call_args.kwargs['success'])
        self.assertIn('costo desconocido', log.call_args.kwargs['error_message'])
