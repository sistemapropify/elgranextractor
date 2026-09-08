"""Pruebas puras y mockeadas del compilador semántico v2."""

from unittest import TestCase
from unittest.mock import patch

from intelligence.reasoning.semantic_compiler import SemanticIntentCompiler


def payload(constraints=None, ambiguities=None):
    return {
        "objective": "search_properties",
        "entity": "property",
        "original_query": "consulta",
        "effective_query": "consulta",
        "constraints": constraints or [],
        "preferences": [],
        "ambiguities": ambiguities or [],
        "assumptions": [],
        "evidence": [],
        "attempts": [],
        "status": "planning",
        "confidence": 0.95,
        "schema_version": "2",
    }


class SemanticIntentCompilerTests(TestCase):
    def test_compiles_field_comparison_and_keeps_vague_term_ambiguous(self):
        compiled = SemanticIntentCompiler.compile_payload(payload(
            constraints=[{
                "id": "c1",
                "left": {"kind": "field", "value": "bathrooms"},
                "operator": "gt",
                "right": {"kind": "field", "value": "bedrooms"},
                "source_text": "más baños que habitaciones",
            }],
            ambiguities=[{
                "id": "a1",
                "concept": "bedrooms",
                "source_text": "pocos cuartos",
                "reason": "No hay máximo explícito",
                "clarification": "¿Cuántos dormitorios como máximo necesitas?",
            }],
        ))

        self.assertTrue(compiled.success)
        self.assertEqual(compiled.task.status.value, "needs_clarification")
        self.assertEqual(compiled.task.constraints[0].right.value, "bedrooms")

    def test_compiles_multiple_districts_as_one_set_constraint(self):
        compiled = SemanticIntentCompiler.compile_payload(payload(
            constraints=[{
                "id": "c1",
                "left": {"kind": "field", "value": "district"},
                "operator": "in",
                "right": {
                    "kind": "set",
                    "value": ["Cayma", "Yanahuara"],
                },
                "source_text": "Cayma o Yanahuara",
            }],
        ))

        self.assertTrue(compiled.success)
        self.assertEqual(
            compiled.task.constraints[0].right.value,
            ["Cayma", "Yanahuara"],
        )

    def test_rejects_hallucinated_schema_field(self):
        compiled = SemanticIntentCompiler.compile_payload(payload(
            constraints=[{
                "id": "c1",
                "left": {"kind": "field", "value": "school_quality_score"},
                "operator": "gte",
                "right": {"kind": "literal", "value": 8},
            }],
        ))

        self.assertFalse(compiled.success)
        self.assertEqual(compiled.status, "invalid")
        self.assertIn(
            "UNKNOWN_FIELD",
            {item.code for item in compiled.validation.issues},
        )

    @patch(
        "intelligence.reasoning.semantic_compiler."
        "SemanticIntentCompiler._call_llm"
    )
    def test_compile_uses_full_structured_response(self, mock_call):
        mock_call.return_value = (
            True,
            "ok",
            {"content": payload(constraints=[{
                "id": "c1",
                "left": {"kind": "field", "value": "land_area"},
                "operator": "gte",
                "right": {"kind": "literal", "value": 200, "unit": "m2"},
                "source_text": "más de 200 metros",
            }])},
        )

        compiled = SemanticIntentCompiler.compile(
            query="terrenos con más de 200 metros",
            active_task={"objective": "search_properties"},
        )

        self.assertTrue(compiled.success)
        self.assertEqual(compiled.task.constraints[0].left.value, "land_area")
        prompt = mock_call.call_args.kwargs["messages"][0]["content"]
        self.assertIn("CONTEXTO", prompt)
        self.assertIn("active_task", prompt)

    @patch(
        "intelligence.reasoning.semantic_compiler."
        "SemanticIntentCompiler._call_llm"
    )
    def test_malformed_model_output_fails_closed(self, mock_call):
        mock_call.return_value = (True, "ok", {"content": "sin json"})

        compiled = SemanticIntentCompiler.compile(query="busca casas")

        self.assertFalse(compiled.success)
        self.assertEqual(compiled.status, "failed")
