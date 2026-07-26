from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.learning.trace_context import (
    bind_trace_id,
    current_trace_id,
    release_trace_id,
)
from intelligence.models import AIConsumptionLog


class AICostTraceCorrelationTests(SimpleTestCase):
    def test_consumption_log_inherits_bound_trace_id(self):
        token = bind_trace_id('trace-query-123')
        try:
            with patch.object(
                AIConsumptionLog.objects,
                'create',
                side_effect=lambda **kwargs: kwargs,
            ):
                log = AIConsumptionLog.registrar_llamada(
                    prompt_tokens=1000,
                    completion_tokens=500,
                    total_tokens=1500,
                )
        finally:
            release_trace_id(token)

        self.assertEqual(log['trace_id'], 'trace-query-123')
        self.assertGreater(log['estimated_cost_usd'], 0)
        self.assertEqual(current_trace_id(), '')

    def test_explicit_trace_id_has_priority(self):
        token = bind_trace_id('ambient-trace')
        try:
            with patch.object(
                AIConsumptionLog.objects,
                'create',
                side_effect=lambda **kwargs: kwargs,
            ):
                log = AIConsumptionLog.registrar_llamada(
                    trace_id='explicit-trace',
                    total_tokens=10,
                )
        finally:
            release_trace_id(token)

        self.assertEqual(log['trace_id'], 'explicit-trace')
