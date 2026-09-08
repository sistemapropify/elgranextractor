import unittest

from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    TaskObjective,
)
from intelligence.reasoning.planner import SemanticPrePlanCritic
from intelligence.reasoning.replanner import ReplanAction, SemanticReplanner
from intelligence.reasoning.result_critic import SemanticResultCritic


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
        confidence=0.95,
    )


class SemanticReplannerTests(unittest.TestCase):
    def test_partial_pass_requires_only_post_filter(self):
        task = semantic_task()
        plan = SemanticPrePlanCritic.build(task)
        report = SemanticResultCritic.evaluate(
            task,
            [
                {"property_type_name": "Terreno", "land_area": 250},
                {"property_type_name": "Terreno", "land_area": 150},
            ],
        )

        decision = SemanticReplanner.decide(task, plan, report)

        self.assertEqual(decision.action, ReplanAction.APPLY_POST_FILTER)
        self.assertFalse(decision.should_retry)

    def test_empty_unverified_requests_broad_inventory_once(self):
        task = semantic_task()
        plan = SemanticPrePlanCritic.build(task)
        report = SemanticResultCritic.evaluate(task, [])

        decision = SemanticReplanner.decide(task, plan, report)

        self.assertEqual(decision.action, ReplanAction.RETRY_BROAD_INVENTORY)
        self.assertTrue(decision.should_retry)
        self.assertIn("land_area", decision.requested_fields)

    def test_missing_field_requests_enrichment(self):
        task = semantic_task()
        plan = SemanticPrePlanCritic.build(task)
        report = SemanticResultCritic.evaluate(
            task,
            [{"property_type_name": "Terreno"}],
        )

        decision = SemanticReplanner.decide(task, plan, report)

        self.assertEqual(decision.action, ReplanAction.ENRICH_REQUIRED_FIELDS)
        self.assertTrue(decision.should_retry)
        self.assertEqual(decision.requested_fields, ["land_area"])

    def test_verified_empty_does_not_retry(self):
        task = semantic_task()
        plan = SemanticPrePlanCritic.build(task)
        report = SemanticResultCritic.evaluate(
            task,
            [],
            inventory_complete=True,
        )

        decision = SemanticReplanner.decide(task, plan, report)

        self.assertEqual(decision.action, ReplanAction.NONE)
        self.assertFalse(decision.should_retry)

    def test_second_failure_stops_loop(self):
        task = semantic_task()
        plan = SemanticPrePlanCritic.build(task)
        report = SemanticResultCritic.evaluate(task, [])

        decision = SemanticReplanner.decide(
            task,
            plan,
            report,
            attempts_used=1,
        )

        self.assertEqual(decision.action, ReplanAction.STOP)
        self.assertFalse(decision.should_retry)
        self.assertIn("SEMANTIC_REPLAN_LIMIT_REACHED", decision.signals)


if __name__ == "__main__":
    unittest.main()
