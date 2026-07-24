from types import SimpleNamespace

from django.test import SimpleTestCase

from intelligence.learning_views import _agentic_quality_metrics


def event(event_type, **payload):
    return SimpleNamespace(event_type=event_type, payload=payload)


class AgenticQualityMetricsTests(SimpleTestCase):
    def test_aggregates_semantic_and_advisory_events(self):
        metrics = _agentic_quality_metrics([
            event('evaluation.semantic.completed', status='completed',
                  disagrees_with_deterministic=True),
            event('evaluation.semantic.completed', status='completed',
                  disagrees_with_deterministic=False),
            event('evaluation.semantic.completed', status='failed'),
            event('evaluation.advisory.decided', authority_applied=True,
                  action='clarify'),
            event('evaluation.advisory.decided', authority_applied=True,
                  action='replan'),
            event('evaluation.advisory.decided', authority_applied=False,
                  action='none'),
        ])

        self.assertEqual(metrics['semantic_total'], 3)
        self.assertEqual(metrics['semantic_completed'], 2)
        self.assertEqual(metrics['semantic_failed'], 1)
        self.assertEqual(metrics['semantic_disagreements'], 1)
        self.assertEqual(metrics['semantic_disagreement_pct'], 50.0)
        self.assertEqual(metrics['advisory_total'], 3)
        self.assertEqual(metrics['advisory_applied'], 2)
        self.assertEqual(metrics['advisory_clarify'], 1)
        self.assertEqual(metrics['advisory_replan'], 1)
        self.assertEqual(metrics['advisory_application_pct'], 66.7)

    def test_empty_event_set_returns_zero_rates(self):
        metrics = _agentic_quality_metrics([])
        self.assertEqual(metrics['semantic_disagreement_pct'], 0)
        self.assertEqual(metrics['advisory_application_pct'], 0)
