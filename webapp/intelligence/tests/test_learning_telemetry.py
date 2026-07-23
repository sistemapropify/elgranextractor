from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.test import override_settings

from intelligence.learning.redaction import (
    normalized_query_hash,
    redact_text,
    sanitize_payload,
)


class LearningRedactionTests(SimpleTestCase):
    def test_redacts_contact_and_credentials(self):
        value = (
            "Escribe a agente@example.com o 987654321. "
            "api_key=secreto password=123"
        )
        redacted = redact_text(value)
        self.assertNotIn('agente@example.com', redacted)
        self.assertNotIn('987654321', redacted)
        self.assertNotIn('secreto', redacted)
        self.assertNotIn('password=123', redacted)

    def test_query_hash_is_stable_for_spacing_and_case(self):
        self.assertEqual(
            normalized_query_hash('  Departamento   EN Cayma '),
            normalized_query_hash('departamento en cayma'),
        )

    def test_payload_uses_allowlist(self):
        payload = sanitize_payload({
            'result_count': 4,
            'orchestration_mode': 'agent_graph',
            'raw_prompt': 'no debe guardarse',
            'token': 'no debe guardarse',
        })
        self.assertEqual(payload['result_count'], 4)
        self.assertNotIn('raw_prompt', payload)
        self.assertNotIn('token', payload)


class LearningEventsFailureSafetyTests(SimpleTestCase):
    @patch('intelligence.learning.events.SystemTrace.objects.create')
    def test_start_trace_failure_does_not_break_chat(self, create):
        from intelligence.learning.events import start_trace

        create.side_effect = RuntimeError('database unavailable')
        trace = start_trace(query='casa en Cayma')
        self.assertIsNone(trace)

    @patch('intelligence.learning.events.emit_event')
    def test_fallback_finishes_as_degraded(self, emit_event):
        from intelligence.learning.events import complete_trace

        trace = SimpleNamespace(
            status='started',
            technical_success=False,
            orchestration_mode='',
            result_count=None,
            grounded=None,
            latency_ms=None,
            completed_at=None,
            save=MagicMock(),
        )
        complete_trace(
            trace,
            success=True,
            orchestration_mode='langgraph_fallback',
            result_count=15,
            latency_ms=1200,
        )
        self.assertEqual(trace.status, 'completed_degraded')
        trace.save.assert_called_once()

    @patch('intelligence.learning.events.emit_event')
    def test_suspicious_success_finishes_as_needs_review(self, emit_event):
        from intelligence.learning.events import complete_trace

        trace = SimpleNamespace(
            status='started',
            technical_success=False,
            orchestration_mode='',
            result_count=None,
            grounded=None,
            latency_ms=None,
            completed_at=None,
            save=MagicMock(),
        )
        complete_trace(
            trace,
            success=True,
            orchestration_mode='agent_graph',
            result_count=8,
            grounded=False,
            review_required=True,
        )
        self.assertEqual(trace.status, 'needs_review')


class LearningAuditorTests(SimpleTestCase):
    @override_settings(LEARNING_AI_AUDIT_ALL=False)
    def test_missing_grounding_and_count_require_review(self):
        from intelligence.learning.auditor import audit_interaction

        result = audit_interaction(
            query='departamentos en Cayma',
            response='Encontré tres',
            orchestration_mode='agent_graph',
            result_count=None,
            grounded=None,
            execution_summary=[],
        )

        self.assertEqual(result['audit_verdict'], 'review')
        self.assertIn('MISSING_RESULT_COUNT', result['audit_signals'])
        self.assertIn('GROUNDING_NOT_CONFIRMED', result['audit_signals'])
