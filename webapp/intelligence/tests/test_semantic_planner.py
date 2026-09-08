import unittest

from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticAmbiguity,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    TaskObjective,
    TaskRelationship,
    TaskTransition,
)
from intelligence.reasoning.planner import PlanStatus, SemanticPrePlanCritic


def rule(identifier, field, operator, right):
    return SemanticConstraint(
        id=identifier,
        left=SemanticOperand.field(field),
        operator=operator,
        right=right,
    )


def task(constraints=None, *, ambiguities=None, objective=None, relationship=None):
    return SemanticTaskState(
        objective=objective or TaskObjective.SEARCH_PROPERTIES,
        entity="property",
        original_query="consulta",
        constraints=list(constraints or []),
        ambiguities=list(ambiguities or []),
        transition=TaskTransition(
            relationship=relationship or TaskRelationship.NEW_TASK
        ),
        confidence=0.95,
    )


class SemanticPrePlanCriticTests(unittest.TestCase):
    def test_simple_filters_are_compiled_to_legacy_pushdown(self):
        semantic_task = task([
            rule(
                "type",
                "property_type",
                ConstraintOperator.EQ,
                SemanticOperand.literal("Casa"),
            ),
            rule(
                "price",
                "price",
                ConstraintOperator.LTE,
                SemanticOperand.literal(300000, "USD"),
            ),
        ])

        plan = SemanticPrePlanCritic.build(semantic_task)

        self.assertTrue(plan.executable)
        self.assertEqual(plan.selected_skill, "busqueda_propiedades")
        self.assertEqual(
            plan.legacy_params,
            {"tipo_propiedad": "Casa", "precio_max": 300000},
        )
        self.assertEqual(plan.post_filter_constraint_ids, [])

    def test_field_comparison_is_planned_as_post_filter(self):
        semantic_task = task([
            rule(
                "relation",
                "bathrooms",
                ConstraintOperator.GT,
                SemanticOperand.field("bedrooms"),
            )
        ])

        plan = SemanticPrePlanCritic.build(semantic_task)

        self.assertTrue(plan.executable)
        self.assertEqual(plan.pushdown_constraint_ids, [])
        self.assertEqual(plan.post_filter_constraint_ids, ["relation"])
        self.assertEqual(
            plan.required_result_fields,
            ["bathrooms", "bedrooms"],
        )

    def test_multiple_districts_are_not_reduced_to_one(self):
        semantic_task = task([
            rule(
                "districts",
                "district",
                ConstraintOperator.IN,
                SemanticOperand.values(["Cayma", "Yanahuara"]),
            )
        ])

        plan = SemanticPrePlanCritic.build(semantic_task)

        self.assertNotIn("distrito", plan.legacy_params)
        self.assertEqual(plan.post_filter_constraint_ids, ["districts"])

    def test_land_area_never_uses_built_area_legacy_parameter(self):
        semantic_task = task([
            rule(
                "land",
                "land_area",
                ConstraintOperator.GT,
                SemanticOperand.literal(200, "m2"),
            )
        ])

        plan = SemanticPrePlanCritic.build(semantic_task)

        self.assertNotIn("area_min", plan.legacy_params)
        self.assertIn("LAND_AREA_MUST_NOT_MAP_TO_BUILT_AREA", plan.signals)

    def test_required_ambiguity_requests_clarification(self):
        semantic_task = task(
            ambiguities=[
                SemanticAmbiguity(
                    id="few_rooms",
                    concept="bedrooms",
                    source_text="pocos cuartos",
                    reason="No hay umbral definido.",
                    clarification="¿Cuántos dormitorios como máximo consideras pocos?",
                )
            ]
        )

        plan = SemanticPrePlanCritic.build(semantic_task)

        self.assertEqual(plan.status, PlanStatus.CLARIFY)
        self.assertFalse(plan.executable)
        self.assertEqual(len(plan.clarification_questions), 1)

    def test_cancelled_task_does_not_execute(self):
        plan = SemanticPrePlanCritic.build(
            task(relationship=TaskRelationship.CANCELLED)
        )

        self.assertEqual(plan.status, PlanStatus.NO_ACTION)
        self.assertFalse(plan.executable)

    def test_unsupported_objective_is_explicit(self):
        plan = SemanticPrePlanCritic.build(
            task(objective=TaskObjective.ANALYZE_MARKET)
        )

        self.assertEqual(plan.status, PlanStatus.UNSUPPORTED)
        self.assertIn(
            "OBJECTIVE_NOT_YET_SUPPORTED_BY_V2_PLANNER",
            plan.signals,
        )


if __name__ == "__main__":
    unittest.main()
