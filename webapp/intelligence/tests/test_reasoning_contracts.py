"""Pruebas puras del contrato semántico agentic v2."""

from unittest import TestCase

from intelligence.reasoning import (
    ConstraintOperator,
    SemanticAmbiguity,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    SemanticTaskValidator,
    TaskObjective,
    TaskStatus,
)


class SemanticReasoningContractTests(TestCase):
    def task(self, constraints=None, ambiguities=None):
        return SemanticTaskState(
            objective=TaskObjective.SEARCH_PROPERTIES,
            entity="property",
            original_query="consulta de prueba",
            constraints=constraints or [],
            ambiguities=ambiguities or [],
        )

    def test_represents_field_to_field_comparison(self):
        task = self.task(constraints=[
            SemanticConstraint(
                id="c1",
                left=SemanticOperand.field("bathrooms"),
                operator=ConstraintOperator.GT,
                right=SemanticOperand.field("bedrooms"),
                source_text="más baños que habitaciones",
            )
        ])

        validation = SemanticTaskValidator.validate(task)

        self.assertTrue(validation.valid)
        self.assertEqual(
            task.constraints[0].right.to_dict(),
            {"kind": "field", "value": "bedrooms", "unit": None},
        )

    def test_represents_multiple_districts_as_set(self):
        task = self.task(constraints=[
            SemanticConstraint(
                id="c1",
                left=SemanticOperand.field("district"),
                operator=ConstraintOperator.IN,
                right=SemanticOperand.values(["Cayma", "Yanahuara"]),
                source_text="en Cayma o Yanahuara",
            )
        ])

        validation = SemanticTaskValidator.validate(task)

        self.assertTrue(validation.valid)
        self.assertEqual(task.constraints[0].right.value, ["Cayma", "Yanahuara"])

    def test_vague_number_is_not_silently_converted_to_literal(self):
        task = self.task(constraints=[
            SemanticConstraint(
                id="c1",
                left=SemanticOperand.field("bedrooms"),
                operator=ConstraintOperator.LTE,
                right=SemanticOperand.literal("pocos"),
                source_text="con pocos cuartos",
            )
        ])

        validation = SemanticTaskValidator.validate(task)

        self.assertFalse(validation.valid)
        self.assertIn(
            "VAGUE_LITERAL_NOT_ALLOWED",
            {item.code for item in validation.issues},
        )

    def test_required_ambiguity_keeps_task_open(self):
        task = self.task(ambiguities=[
            SemanticAmbiguity(
                id="a1",
                concept="bedrooms",
                source_text="pocos cuartos",
                reason="No existe un límite numérico",
                clarification="¿Cuál es el máximo de dormitorios que consideras pocos?",
            )
        ])

        status = task.refresh_status()
        validation = SemanticTaskValidator.validate(task)

        self.assertEqual(status, TaskStatus.NEEDS_CLARIFICATION)
        self.assertTrue(validation.valid)

    def test_between_requires_two_limits(self):
        task = self.task(constraints=[
            SemanticConstraint(
                id="c1",
                left=SemanticOperand.field("price"),
                operator=ConstraintOperator.BETWEEN,
                right=SemanticOperand.values([100000]),
            )
        ])

        validation = SemanticTaskValidator.validate(task)

        self.assertFalse(validation.valid)
        self.assertIn(
            "BETWEEN_REQUIRES_TWO_VALUES",
            {item.code for item in validation.issues},
        )

    def test_unknown_fields_are_rejected(self):
        task = self.task(constraints=[
            SemanticConstraint(
                id="c1",
                left=SemanticOperand.field("imaginary_score"),
                operator=ConstraintOperator.GTE,
                right=SemanticOperand.literal(10),
            )
        ])

        validation = SemanticTaskValidator.validate(task)

        self.assertFalse(validation.valid)
        self.assertIn("UNKNOWN_FIELD", {item.code for item in validation.issues})

    def test_round_trip_and_fingerprint_are_stable(self):
        task = self.task(constraints=[
            SemanticConstraint(
                id="c1",
                left=SemanticOperand.field("land_area"),
                operator=ConstraintOperator.GTE,
                right=SemanticOperand.literal(200, unit="m2"),
            )
        ])
        task.refresh_status()

        restored = SemanticTaskState.from_dict(task.to_dict())

        self.assertEqual(restored.to_dict(), task.to_dict())
        self.assertEqual(restored.fingerprint(), task.fingerprint())
