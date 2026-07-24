from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.agents.semantic_advisory_controller import (
    SemanticAdvisoryController,
)


class SemanticAdvisoryControllerTests(SimpleTestCase):
    def semantic(self, verdict, **overrides):
        data = {
            "mode": "advisory",
            "status": "completed",
            "verdict": verdict,
            "confidence": 0.96,
            "reason": "La ejecución no está suficientemente respaldada.",
            "signals": [],
            "missing_information": [],
        }
        data.update(overrides)
        return data

    def decide(self, semantic, retries=0, plan=None):
        return SemanticAdvisoryController.decide(
            semantic_evaluation=semantic,
            deterministic_evaluation={"verdict": "pass"},
            search_plan=plan or {
                "query": "terrenos en Cayma",
                "collections": ["propiedadespropify"],
                "conditions": [],
            },
            retries_used=retries,
        )

    def test_shadow_mode_never_applies_authority(self):
        semantic = self.semantic(
            "block",
            mode="shadow",
            signals=["UNGROUNDED_RESULTS"],
        )
        decision = self.decide(semantic)

        self.assertFalse(decision["authority_applied"])
        self.assertEqual(decision["action"], "none")

    @patch.dict("os.environ", {"EXECUTION_JUDGE_MIN_CONFIDENCE": "0.90"})
    def test_high_confidence_clarification_is_allowed(self):
        decision = self.decide(self.semantic(
            "clarify",
            missing_information=["presupuesto máximo", "área mínima"],
        ))

        self.assertTrue(decision["authority_applied"])
        self.assertEqual(decision["action"], "clarify")
        self.assertIn("presupuesto máximo", decision["clarification_question"])

    def test_replan_reuses_canonical_plan_once(self):
        plan = {
            "query": "terrenos en Cayma",
            "collections": ["propiedadespropify"],
            "conditions": [{"logical_name": "distrito", "value": "Cayma"}],
        }
        first = self.decide(self.semantic("replan"), plan=plan)
        second = self.decide(self.semantic("replan"), retries=1, plan=plan)

        self.assertTrue(first["authority_applied"])
        self.assertEqual(first["suggested_plan"], plan)
        self.assertFalse(second["authority_applied"])

    def test_block_requires_allowlisted_risk_signal(self):
        denied = self.decide(self.semantic("block", signals=["VAGUE concern"]))
        allowed = self.decide(self.semantic(
            "block",
            signals=["UNGROUNDED_RESULTS"],
        ))

        self.assertFalse(denied["authority_applied"])
        self.assertTrue(allowed["authority_applied"])
        self.assertEqual(allowed["action"], "block")

    def test_low_confidence_never_applies_authority(self):
        decision = self.decide(self.semantic(
            "clarify",
            confidence=0.70,
            missing_information=["distrito"],
        ))

        self.assertFalse(decision["authority_applied"])

    def test_pass_reports_operational_judge_without_intervention(self):
        decision = self.decide(self.semantic("pass", confidence=0.97))

        self.assertFalse(decision["authority_applied"])
        self.assertEqual(decision["judge_status"], "completed")
        self.assertEqual(decision["judge_verdict"], "pass")
        self.assertIn("aprobó", decision["reason"])
