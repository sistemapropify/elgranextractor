import unittest

from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    TaskObjective,
)
from intelligence.reasoning.result_critic import (
    ResultCriticStatus,
    SemanticResultCritic,
)


def task(*constraints):
    return SemanticTaskState(
        objective=TaskObjective.SEARCH_PROPERTIES,
        entity="property",
        original_query="consulta",
        constraints=list(constraints),
        confidence=0.95,
    )


def rule(identifier, field, operator, right):
    return SemanticConstraint(
        id=identifier,
        left=SemanticOperand.field(field),
        operator=operator,
        right=right,
    )


class SemanticResultCriticTests(unittest.TestCase):
    def test_returns_only_indexes_matching_all_constraints(self):
        semantic_task = task(
            rule(
                "type",
                "property_type",
                ConstraintOperator.EQ,
                SemanticOperand.literal("Terreno"),
            ),
            rule(
                "area",
                "land_area",
                ConstraintOperator.GT,
                SemanticOperand.literal(200),
            ),
        )
        results = [
            {"id": 1, "property_type_name": "Terreno", "land_area": 250},
            {"id": 2, "property_type_name": "Terreno", "land_area": 180},
            {"id": 3, "property_type_name": "Casa", "land_area": 300},
        ]

        report = SemanticResultCritic.evaluate(semantic_task, results)

        self.assertEqual(report.status, ResultCriticStatus.PASS)
        self.assertEqual(report.matched_indexes, [0])
        self.assertEqual(
            [item["id"] for item in SemanticResultCritic.matching_results(
                results, report
            )],
            [1],
        )

    def test_field_comparison_is_checked_on_real_results(self):
        semantic_task = task(
            rule(
                "relation",
                "bathrooms",
                ConstraintOperator.GT,
                SemanticOperand.field("bedrooms"),
            )
        )

        report = SemanticResultCritic.evaluate(
            semantic_task,
            [
                {"bedrooms": 3, "bathrooms": 2},
                {"bedrooms": 2, "bathrooms": 3},
            ],
        )

        self.assertEqual(report.status, ResultCriticStatus.PASS)
        self.assertEqual(report.matched_indexes, [1])

    def test_zero_results_are_not_automatically_approved(self):
        report = SemanticResultCritic.evaluate(
            task(
                rule(
                    "district",
                    "district",
                    ConstraintOperator.EQ,
                    SemanticOperand.literal("Cayma"),
                )
            ),
            [],
        )

        self.assertEqual(report.status, ResultCriticStatus.EMPTY_UNVERIFIED)
        self.assertFalse(report.publishable)
        self.assertIn("ZERO_RESULTS_REQUIRE_INVENTORY_PROOF", report.signals)

    def test_exhaustive_zero_results_can_be_verified(self):
        report = SemanticResultCritic.evaluate(
            task(),
            [],
            inventory_complete=True,
        )

        self.assertEqual(report.status, ResultCriticStatus.NO_MATCH_VERIFIED)
        self.assertTrue(report.publishable)

    def test_missing_required_fields_are_insufficient_evidence(self):
        semantic_task = task(
            rule(
                "area",
                "land_area",
                ConstraintOperator.GT,
                SemanticOperand.literal(200),
            )
        )

        report = SemanticResultCritic.evaluate(
            semantic_task,
            [{"title": "Terreno sin specs"}],
        )

        self.assertEqual(
            report.status,
            ResultCriticStatus.INSUFFICIENT_EVIDENCE,
        )
        self.assertIn("REQUIRED_RESULT_FIELDS_MISSING", report.signals)

    def test_rows_violating_filters_are_reported_as_mismatch(self):
        semantic_task = task(
            rule(
                "type",
                "property_type",
                ConstraintOperator.EQ,
                SemanticOperand.literal("Terreno"),
            )
        )

        report = SemanticResultCritic.evaluate(
            semantic_task,
            [{"property_type_name": "Departamento"}],
        )

        self.assertEqual(report.status, ResultCriticStatus.RESULT_MISMATCH)
        self.assertFalse(report.publishable)
        self.assertIn(
            "RETURNED_RESULTS_VIOLATE_SEMANTIC_CONSTRAINTS",
            report.signals,
        )

    def test_exhaustive_inventory_with_no_match_is_verified(self):
        semantic_task = task(
            rule(
                "district",
                "district",
                ConstraintOperator.EQ,
                SemanticOperand.literal("Cayma"),
            )
        )

        report = SemanticResultCritic.evaluate(
            semantic_task,
            [{"district_name": "Sachaca"}],
            inventory_complete=True,
        )

        self.assertEqual(report.status, ResultCriticStatus.NO_MATCH_VERIFIED)
        self.assertTrue(report.publishable)


if __name__ == "__main__":
    unittest.main()
