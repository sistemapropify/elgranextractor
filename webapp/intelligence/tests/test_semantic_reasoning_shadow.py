import os
import unittest
from unittest.mock import patch

from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    TaskObjective,
)
from intelligence.reasoning.semantic_compiler import SemanticCompilationResult
from intelligence.reasoning.semantic_shadow import SemanticReasoningShadow
from intelligence.reasoning.validators import ValidationResult


def compiled_task(*constraints):
    return SemanticCompilationResult(
        status="completed",
        task=SemanticTaskState(
            original_query="consulta",
            objective=TaskObjective.SEARCH_PROPERTIES,
            entity="property",
            constraints=list(constraints),
            confidence=0.94,
        ),
        validation=ValidationResult(),
    )


class SemanticReasoningShadowTests(unittest.TestCase):
    @patch.dict(os.environ, {"SEMANTIC_REASONING_MODE": "off"})
    @patch(
        "intelligence.reasoning.semantic_shadow."
        "SemanticIntentCompiler.compile"
    )
    def test_off_does_not_call_model(self, compile_mock):
        result = SemanticReasoningShadow.observe(
            query="casas", active_task=None, search_plan=None
        )

        self.assertFalse(result["enabled"])
        self.assertEqual(result["status"], "disabled")
        compile_mock.assert_not_called()

    @patch.dict(os.environ, {"SEMANTIC_REASONING_MODE": "shadow"})
    @patch(
        "intelligence.reasoning.semantic_shadow."
        "SemanticIntentCompiler.compile"
    )
    def test_shadow_reports_meaning_lost_by_legacy_plan(self, compile_mock):
        compile_mock.return_value = compiled_task(
            SemanticConstraint(
                id="districts",
                left=SemanticOperand.field("district"),
                operator=ConstraintOperator.IN,
                right=SemanticOperand.values(["Cayma", "Yanahuara"]),
            ),
            SemanticConstraint(
                id="comparison",
                left=SemanticOperand.field("bathrooms"),
                operator=ConstraintOperator.GT,
                right=SemanticOperand.field("bedrooms"),
            ),
        )
        plan = {
            "conditions": [{
                "field_name": "district_name",
                "operator": "eq",
                "value": "Cayma",
            }]
        }

        result = SemanticReasoningShadow.observe(
            query="en Cayma o Yanahuara con más baños que habitaciones",
            active_task=None,
            search_plan=plan,
        )

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["authority_applied"])
        self.assertEqual(result["metrics"]["missing_constraint_count"], 1)
        self.assertEqual(result["metrics"]["unsupported_constraint_count"], 1)
        self.assertIn("LEGACY_PLAN_SEMANTIC_GAP", result["signals"])
        self.assertIn(
            "LEGACY_PLAN_UNSUPPORTED_RELATION",
            result["signals"],
        )

    @patch.dict(os.environ, {"SEMANTIC_REASONING_MODE": "shadow"})
    @patch(
        "intelligence.reasoning.semantic_shadow."
        "SemanticIntentCompiler.compile"
    )
    def test_shadow_recognizes_constraint_preserved_by_plan(self, compile_mock):
        compile_mock.return_value = compiled_task(
            SemanticConstraint(
                id="bedrooms",
                left=SemanticOperand.field("bedrooms"),
                operator=ConstraintOperator.GTE,
                right=SemanticOperand.literal(3),
            )
        )
        plan = {
            "conditions": [{
                "field_name": "bedrooms",
                "operator": "gte",
                "value": 3,
            }]
        }

        result = SemanticReasoningShadow.observe(
            query="mínimo 3 habitaciones",
            active_task=None,
            search_plan=plan,
        )

        self.assertEqual(result["metrics"]["represented_constraint_count"], 1)
        self.assertEqual(result["metrics"]["missing_constraint_count"], 0)
        self.assertEqual(result["signals"], [])

    @patch.dict(os.environ, {"SEMANTIC_REASONING_MODE": "shadow"})
    @patch(
        "intelligence.reasoning.semantic_shadow."
        "SemanticIntentCompiler.compile",
        side_effect=RuntimeError("servicio no disponible"),
    )
    def test_compiler_failure_never_breaks_chat(self, _compile_mock):
        result = SemanticReasoningShadow.observe(
            query="casas", active_task=None, search_plan={}
        )

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["authority_applied"])
        self.assertIn("SEMANTIC_COMPILER_EXCEPTION", result["signals"])


if __name__ == "__main__":
    unittest.main()
