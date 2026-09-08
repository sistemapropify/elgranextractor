import unittest

from intelligence.reasoning.constraint_engine import SemanticConstraintEngine
from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticConstraint,
    SemanticOperand,
)


def constraint(identifier, field, operator, right, *, required=True):
    return SemanticConstraint(
        id=identifier,
        left=SemanticOperand.field(field),
        operator=operator,
        right=right,
        required=required,
    )


class SemanticConstraintEngineTests(unittest.TestCase):
    def test_field_to_field_comparison(self):
        rule = constraint(
            "more_bathrooms",
            "bathrooms",
            ConstraintOperator.GT,
            SemanticOperand.field("bedrooms"),
        )

        passed = SemanticConstraintEngine.evaluate(
            {"bedrooms": 2, "bathrooms": 3}, [rule]
        )
        failed = SemanticConstraintEngine.evaluate(
            {"bedrooms": 3, "bathrooms": 2}, [rule]
        )

        self.assertTrue(passed.matched)
        self.assertFalse(failed.matched)

    def test_multiple_districts_use_in_operator(self):
        rule = constraint(
            "districts",
            "district",
            ConstraintOperator.IN,
            SemanticOperand.values(["Cayma", "Yanahuara"]),
        )

        self.assertTrue(
            SemanticConstraintEngine.evaluate(
                {"district_name": "YANAHUARA"}, [rule]
            ).matched
        )
        self.assertFalse(
            SemanticConstraintEngine.evaluate(
                {"district_name": "Sachaca"}, [rule]
            ).matched
        )

    def test_between_is_inclusive(self):
        rule = constraint(
            "area_range",
            "land_area",
            ConstraintOperator.BETWEEN,
            SemanticOperand.values([150, 300]),
        )

        self.assertTrue(
            SemanticConstraintEngine.evaluate({"land_area": 150}, [rule]).matched
        )
        self.assertTrue(
            SemanticConstraintEngine.evaluate({"land_area": 300}, [rule]).matched
        )
        self.assertFalse(
            SemanticConstraintEngine.evaluate({"land_area": 301}, [rule]).matched
        )

    def test_missing_required_field_rejects_entity(self):
        rule = constraint(
            "bedrooms",
            "bedrooms",
            ConstraintOperator.GTE,
            SemanticOperand.literal(3),
        )

        evaluation = SemanticConstraintEngine.evaluate({"title": "Casa"}, [rule])

        self.assertFalse(evaluation.matched)
        self.assertEqual(evaluation.checks[0].status, "missing_operand")

    def test_missing_optional_field_does_not_reject_entity(self):
        rule = constraint(
            "optional_garage",
            "garage_spaces",
            ConstraintOperator.GTE,
            SemanticOperand.literal(1),
            required=False,
        )

        evaluation = SemanticConstraintEngine.evaluate({"title": "Casa"}, [rule])

        self.assertTrue(evaluation.matched)
        self.assertEqual(evaluation.checks[0].status, "missing_operand")

    def test_text_comparison_is_case_and_accent_insensitive(self):
        rule = constraint(
            "district",
            "district",
            ConstraintOperator.EQ,
            SemanticOperand.literal("José Luis Bustamante y Rivero"),
        )

        evaluation = SemanticConstraintEngine.evaluate(
            {"district_name": "JOSE LUIS BUSTAMANTE Y RIVERO"}, [rule]
        )

        self.assertTrue(evaluation.matched)

    def test_invalid_numeric_value_fails_closed(self):
        rule = constraint(
            "price",
            "price",
            ConstraintOperator.LT,
            SemanticOperand.literal(200000),
        )

        evaluation = SemanticConstraintEngine.evaluate(
            {"price": "consultar"}, [rule]
        )

        self.assertFalse(evaluation.matched)
        self.assertEqual(evaluation.checks[0].status, "invalid_value")

    def test_filter_returns_only_entities_satisfying_all_constraints(self):
        rules = [
            constraint(
                "type",
                "property_type",
                ConstraintOperator.EQ,
                SemanticOperand.literal("Terreno"),
            ),
            constraint(
                "area",
                "land_area",
                ConstraintOperator.GT,
                SemanticOperand.literal(200),
            ),
        ]
        entities = [
            {
                "id": 1,
                "property_type_name": "Terreno",
                "land_area": 250,
            },
            {
                "id": 2,
                "property_type_name": "Terreno",
                "land_area": 180,
            },
            {
                "id": 3,
                "property_type_name": "Departamento",
                "land_area": 300,
            },
        ]

        matched, evaluations = SemanticConstraintEngine.filter(entities, rules)

        self.assertEqual([item["id"] for item in matched], [1])
        self.assertEqual(len(evaluations), 3)


if __name__ == "__main__":
    unittest.main()
