import unittest

from intelligence.reasoning.contracts import (
    ConstraintOperator,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
    TaskObjective,
    TaskRelationship,
    TaskTransition,
)
from intelligence.reasoning.conversation_state import SemanticConversationState


def rule(identifier, field, value):
    return SemanticConstraint(
        id=identifier,
        left=SemanticOperand.field(field),
        operator=ConstraintOperator.EQ,
        right=SemanticOperand.literal(value),
    )


def task(
    constraints,
    *,
    relationship=TaskRelationship.NEW_TASK,
    carried=None,
    added=None,
    removed=None,
    objective=TaskObjective.SEARCH_PROPERTIES,
):
    return SemanticTaskState(
        objective=objective,
        entity="property",
        original_query="consulta",
        constraints=list(constraints),
        transition=TaskTransition(
            relationship=relationship,
            carried_constraint_ids=list(carried or []),
            added_constraint_ids=list(added or []),
            removed_constraint_ids=list(removed or []),
        ),
        confidence=0.95,
    )


class SemanticConversationStateTests(unittest.TestCase):
    def test_creates_new_state_without_mutating_input_metadata(self):
        metadata = {"title": "Consulta"}
        candidate = task([rule("type", "property_type", "Casa")])

        updated, result = SemanticConversationState.apply(metadata, candidate)

        self.assertTrue(result.accepted)
        self.assertEqual(result.action, "create")
        self.assertNotIn(SemanticConversationState.METADATA_KEY, metadata)
        self.assertIsNotNone(SemanticConversationState.load(updated))

    def test_continuation_must_preserve_previous_constraints(self):
        previous = task([
            rule("type", "property_type", "Casa"),
            rule("district", "district", "Cayma"),
        ])
        metadata, _ = SemanticConversationState.apply({}, previous)
        candidate = task(
            [rule("type", "property_type", "Casa")],
            relationship=TaskRelationship.CONTINUATION,
            carried=["type"],
        )

        unchanged, result = SemanticConversationState.apply(metadata, candidate)

        self.assertFalse(result.accepted)
        self.assertIn("PREVIOUS_CONSTRAINT_SILENTLY_LOST", result.issues)
        loaded = SemanticConversationState.load(unchanged)
        self.assertEqual({item.id for item in loaded.constraints}, {"type", "district"})

    def test_explicit_removal_is_accepted(self):
        previous = task([
            rule("type", "property_type", "Casa"),
            rule("district", "district", "Cayma"),
        ])
        metadata, _ = SemanticConversationState.apply({}, previous)
        candidate = task(
            [rule("type", "property_type", "Casa")],
            relationship=TaskRelationship.CORRECTION,
            carried=["type"],
            removed=["district"],
        )

        updated, result = SemanticConversationState.apply(metadata, candidate)

        self.assertTrue(result.accepted)
        self.assertEqual(result.action, "update")
        loaded = SemanticConversationState.load(updated)
        self.assertEqual([item.id for item in loaded.constraints], ["type"])

    def test_added_constraint_must_be_declared(self):
        previous = task([rule("type", "property_type", "Casa")])
        metadata, _ = SemanticConversationState.apply({}, previous)
        candidate = task(
            [
                rule("type", "property_type", "Casa"),
                rule("district", "district", "Yanahuara"),
            ],
            relationship=TaskRelationship.CONTINUATION,
            carried=["type"],
        )

        _updated, result = SemanticConversationState.apply(metadata, candidate)

        self.assertFalse(result.accepted)
        self.assertIn("ADDED_CONSTRAINT_NOT_DECLARED", result.issues)

    def test_declared_addition_is_accepted(self):
        previous = task([rule("type", "property_type", "Casa")])
        metadata, _ = SemanticConversationState.apply({}, previous)
        candidate = task(
            [
                rule("type", "property_type", "Casa"),
                rule("district", "district", "Yanahuara"),
            ],
            relationship=TaskRelationship.CONTINUATION,
            carried=["type"],
            added=["district"],
        )

        updated, result = SemanticConversationState.apply(metadata, candidate)

        self.assertTrue(result.accepted)
        loaded = SemanticConversationState.load(updated)
        self.assertEqual(len(loaded.constraints), 2)

    def test_continuation_without_previous_state_is_rejected(self):
        candidate = task(
            [rule("district", "district", "Cayma")],
            relationship=TaskRelationship.CONTINUATION,
            added=["district"],
        )

        _updated, result = SemanticConversationState.apply({}, candidate)

        self.assertFalse(result.accepted)
        self.assertIn("MISSING_PREVIOUS_TASK", result.issues)

    def test_new_task_replaces_previous_state(self):
        previous = task([rule("type", "property_type", "Casa")])
        metadata, _ = SemanticConversationState.apply({}, previous)
        candidate = task([rule("type2", "property_type", "Terreno")])

        updated, result = SemanticConversationState.apply(metadata, candidate)

        self.assertTrue(result.accepted)
        self.assertEqual(result.action, "replace")
        loaded = SemanticConversationState.load(updated)
        self.assertEqual(loaded.constraints[0].right.value, "Terreno")

    def test_cancelled_task_clears_state(self):
        previous = task([rule("type", "property_type", "Casa")])
        metadata, _ = SemanticConversationState.apply({}, previous)
        cancelled = task(
            [],
            relationship=TaskRelationship.CANCELLED,
        )

        updated, result = SemanticConversationState.apply(metadata, cancelled)

        self.assertTrue(result.accepted)
        self.assertEqual(result.action, "clear")
        self.assertIsNone(SemanticConversationState.load(updated))

    def test_corrupt_metadata_is_ignored(self):
        metadata = {
            SemanticConversationState.METADATA_KEY: {
                "objective": "invented",
                "entity": "property",
            }
        }

        self.assertIsNone(SemanticConversationState.load(metadata))


if __name__ == "__main__":
    unittest.main()
