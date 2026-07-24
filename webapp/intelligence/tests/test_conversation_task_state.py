from django.test import SimpleTestCase

from intelligence.agents.execution_evaluator import ExecutionEvaluator
from intelligence.search.normalizer import SearchPlanNormalizer
from intelligence.services.conversation_task_state import ConversationTaskState


class ConversationTaskStateTests(SimpleTestCase):
    def test_school_clarification_is_kept_open_until_required_slots_exist(self):
        task = ConversationTaskState.from_message(
            "Propiedades ideales para construir un colegio"
        )

        self.assertEqual(task["status"], "collecting_requirements")
        self.assertCountEqual(
            task["missing_fields"],
            ["distrito", "area_min", "cantidad_alumnos"],
        )

        metadata = {ConversationTaskState.METADATA_KEY: task}
        effective, updated, relationship = ConversationTaskState.resolve(
            metadata,
            "En Cayma con un área de 500 metros y para 300 alumnos",
        )

        self.assertEqual(relationship, "continuation")
        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["collected_fields"]["distrito"], "Cayma")
        self.assertEqual(updated["collected_fields"]["area_min"], 500)
        self.assertEqual(updated["collected_fields"]["cantidad_alumnos"], 300)
        self.assertIn("construir un colegio", effective)

    def test_explicit_property_query_starts_new_task(self):
        task = ConversationTaskState.from_message(
            "Propiedades ideales para construir un colegio"
        )
        effective, updated, relationship = ConversationTaskState.resolve(
            {ConversationTaskState.METADATA_KEY: task},
            "Ahora muéstrame departamentos en Yanahuara",
        )

        self.assertEqual(relationship, "new_task")
        self.assertIsNone(updated)
        self.assertEqual(effective, "Ahora muéstrame departamentos en Yanahuara")

    def test_simple_query_has_no_pending_task(self):
        self.assertIsNone(
            ConversationTaskState.from_message("Muéstrame terrenos en Cayma")
        )


class SchoolSearchContractTests(SimpleTestCase):
    def test_normalizer_extracts_school_candidate_filters(self):
        params = SearchPlanNormalizer.params_from_message(
            "Buscar candidatos para construir un colegio en Cayma "
            "con área mínima de 500 m² para 300 alumnos"
        )

        self.assertEqual(params["distrito"], "Cayma")
        self.assertEqual(params["tipo_propiedad"], "Terreno")
        self.assertEqual(params["condicion"], "Disponible")
        self.assertEqual(float(params["area_min"]), 500.0)

    def test_preflight_allows_complete_candidate_contract(self):
        message = (
            "Buscar terrenos candidatos para construir un colegio en Cayma "
            "con área mínima de 500 m² para 300 alumnos"
        )
        params = SearchPlanNormalizer.params_from_message(message)
        plan = SearchPlanNormalizer.from_params(
            query=message,
            params=params,
            collections=["propiedadespropify"],
        ).to_dict()

        evaluation = ExecutionEvaluator.evaluate(
            message=message,
            results={},
            search_plan=plan,
        )

        self.assertEqual(evaluation.verdict, "pass")
        self.assertIn("SUITABILITY_CANDIDATE_SEARCH", evaluation.signals)

    def test_post_evaluation_blocks_incompatible_department(self):
        message = (
            "Buscar terrenos candidatos para construir un colegio en Cayma "
            "con área mínima de 500 m² para 300 alumnos"
        )
        params = SearchPlanNormalizer.params_from_message(message)
        plan = SearchPlanNormalizer.from_params(
            query=message,
            params=params,
            collections=["propiedadespropify"],
        ).to_dict()
        results = {
            "agente_propiedades": {
                "success": True,
                "requirements": [],
                "final_answer": [{
                    "field_values": {
                        "district_name": "Cayma",
                        "property_type_name": "Departamento",
                        "property_status_name": "Disponible",
                        "built_area": 600,
                    }
                }],
            }
        }

        evaluation = ExecutionEvaluator.evaluate(
            message=message,
            results=results,
            search_plan=plan,
        )

        self.assertEqual(evaluation.verdict, "block")
        self.assertIn("SEARCH_PLAN_FILTER_MISMATCH", evaluation.signals)
