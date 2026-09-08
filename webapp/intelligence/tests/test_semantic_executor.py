import unittest

from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    TaskObjective,
)
from intelligence.reasoning.planner import SemanticPrePlanCritic
from intelligence.reasoning.semantic_executor import (
    SemanticExecutionExecutor,
    SemanticRetryResult,
)


def semantic_task():
    return SemanticTaskState(
        objective=TaskObjective.SEARCH_PROPERTIES,
        entity="property",
        original_query="terrenos con más de 200 m2",
        constraints=[
            SemanticConstraint(
                id="type",
                left=SemanticOperand.field("property_type"),
                operator=ConstraintOperator.EQ,
                right=SemanticOperand.literal("Terreno"),
            ),
            SemanticConstraint(
                id="area",
                left=SemanticOperand.field("land_area"),
                operator=ConstraintOperator.GT,
                right=SemanticOperand.literal(200),
            ),
        ],
        confidence=0.98,
    )


class SemanticExecutionExecutorTests(unittest.TestCase):
    def test_understands_standard_skill_envelope(self):
        outcome = SemanticExecutionExecutor.execute(
            semantic_task(),
            [{"source_id": "9", "field_values": {
                "property_type_name": "Terreno", "land_area": 240,
            }}],
            mode="enforced",
        )
        self.assertTrue(outcome.publishable)
        self.assertTrue(outcome.authority_applied)
        self.assertEqual(len(outcome.final_results), 1)

    def test_enforced_postfilter_removes_non_matching_rows(self):
        results = [
            {"field_values": {"property_type_name": "Terreno", "land_area": 260}},
            {"field_values": {"property_type_name": "Terreno", "land_area": 180}},
        ]
        outcome = SemanticExecutionExecutor.execute(
            semantic_task(), results, mode="enforced",
        )
        self.assertTrue(outcome.authority_applied)
        self.assertEqual(len(outcome.final_results), 1)
        self.assertEqual(
            outcome.final_results[0]["field_values"]["land_area"], 260,
        )

    def test_shadow_never_retries_or_applies_authority(self):
        called = []
        def retry(*_args):
            called.append(True)
            return SemanticRetryResult(success=True, inventory_complete=True)
        outcome = SemanticExecutionExecutor.execute(
            semantic_task(), [], mode="shadow", retry=retry,
        )
        self.assertFalse(called)
        self.assertFalse(outcome.authority_applied)
        self.assertIn("SEMANTIC_RETRY_OBSERVED_ONLY", outcome.signals)

    def test_advisory_retries_but_does_not_apply_authority(self):
        calls = []
        def retry(task, plan, decision):
            calls.append((task.fingerprint(), decision.task_hash))
            return SemanticRetryResult(
                success=True, inventory_complete=True,
                results=[{"field_values": {
                    "property_type_name": "Terreno", "land_area": 350,
                }}],
            )
        task = semantic_task()
        outcome = SemanticExecutionExecutor.execute(
            task, [], mode="advisory", retry=retry,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], calls[0][1])
        self.assertTrue(outcome.publishable)
        self.assertFalse(outcome.authority_applied)
        self.assertEqual(outcome.attempts_used, 1)

    def test_enforced_retry_can_verify_empty_inventory(self):
        def retry(*_args):
            return SemanticRetryResult(
                success=True, results=[], inventory_complete=True,
            )
        outcome = SemanticExecutionExecutor.execute(
            semantic_task(), [], mode="enforced", retry=retry,
        )
        self.assertEqual(outcome.status, "verified_empty")
        self.assertTrue(outcome.publishable)
        self.assertTrue(outcome.authority_applied)
        self.assertEqual(outcome.attempts_used, 1)

    def test_retry_is_never_repeated(self):
        calls = []
        def retry(*_args):
            calls.append(True)
            return SemanticRetryResult(
                success=True,
                results=[{"field_values": {
                    "property_type_name": "Casa", "land_area": 50,
                }}],
                inventory_complete=False,
            )
        outcome = SemanticExecutionExecutor.execute(
            semantic_task(), [], mode="enforced", retry=retry,
        )
        self.assertEqual(len(calls), 1)
        self.assertFalse(outcome.publishable)
        self.assertFalse(outcome.authority_applied)
        self.assertIn("SEMANTIC_REPLAN_LIMIT_REACHED", outcome.signals)

    def test_broad_retry_omits_risky_numeric_pushdowns(self):
        plan = SemanticPrePlanCritic.build(semantic_task())
        params = SemanticExecutionExecutor.broad_retry_params(plan)
        self.assertEqual(params["tipo_propiedad"], "Terreno")
        self.assertNotIn("area_min", params)
        self.assertTrue(params["_semantic_inventory_scan"])
        self.assertEqual(params["top_k"], 0)


if __name__ == "__main__":
    unittest.main()
