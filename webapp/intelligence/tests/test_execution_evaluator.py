from django.test import SimpleTestCase

from intelligence.agents.execution_evaluator import ExecutionEvaluator


def agent_result(items):
    return {
        'agente_propiedades': {
            'success': True,
            'final_answer': items,
            'requirements': [],
        }
    }


class ExecutionEvaluatorTests(SimpleTestCase):
    def test_clarifies_school_suitability_instead_of_returning_inventory(self):
        items = [
            {
                'source_id': index,
                'field_values': {'property_type_name': 'Departamento'},
            }
            for index in range(147)
        ]

        evaluation = ExecutionEvaluator.evaluate(
            message='Muéstrame propiedades ideales para construir un colegio',
            results=agent_result(items),
        )

        self.assertEqual(evaluation.verdict, 'clarify')
        self.assertIn('SPECIALIZED_SUITABILITY_REQUIRED', evaluation.signals)
        self.assertIn('BROAD_RESULT_SET', evaluation.signals)
        self.assertIn('área mínima', evaluation.clarification_question)

    def test_passes_small_relevant_property_result(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Muéstrame terrenos en Cayma',
            results=agent_result([{
                'source_id': 1,
                'field_values': {
                    'property_type_name': 'Terreno',
                    'district_name': 'Cayma',
                },
            }]),
        )
        self.assertEqual(evaluation.verdict, 'pass')

    def test_replans_when_explicit_type_is_violated(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Muéstrame terrenos',
            results=agent_result([{
                'source_id': 1,
                'field_values': {'property_type_name': 'Departamento'},
            }]),
            search_plan={
                'query': 'Muéstrame terrenos',
                'collections': ['propiedadespropify'],
                'conditions': [],
            },
        )
        self.assertEqual(evaluation.verdict, 'replan')
        self.assertEqual(
            evaluation.suggested_plan['conditions'][0]['value'],
            'Terreno',
        )

    def test_blocks_persistent_type_mismatch_after_retry(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Muéstrame terrenos',
            results=agent_result([{
                'source_id': 1,
                'field_values': {'property_type_name': 'Departamento'},
            }]),
            attempt=1,
        )
        self.assertEqual(evaluation.verdict, 'block')

    def test_clarifies_unfiltered_broad_inventory(self):
        items = [{'source_id': index, 'field_values': {}} for index in range(51)]
        evaluation = ExecutionEvaluator.evaluate(
            message='Muéstrame propiedades',
            results=agent_result(items),
        )
        self.assertEqual(evaluation.verdict, 'clarify')
        self.assertIn('LOW_SELECTIVITY', evaluation.signals)

    def test_replans_when_bedrooms_from_plan_are_violated(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Departamentos con 3 habitaciones en Cayma',
            results=agent_result([{
                'source_id': 1,
                'field_values': {
                    'property_type_name': 'Departamento',
                    'district_name': 'Cayma',
                    'bedrooms': 2,
                },
            }]),
            search_plan={
                'query': 'Departamentos con 3 habitaciones en Cayma',
                'collections': ['propiedadespropify'],
                'conditions': [
                    {'logical_name': 'distrito', 'value': 'Cayma'},
                    {'logical_name': 'tipo_propiedad', 'value': 'Departamento'},
                    {'logical_name': 'habitaciones', 'value': 3},
                ],
            },
        )

        self.assertEqual(evaluation.verdict, 'replan')
        self.assertIn('SEARCH_PLAN_FILTER_MISMATCH', evaluation.signals)

    def test_replans_when_area_max_is_violated(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Terrenos en Cayma con menos de 500 metros',
            results=agent_result([{
                'field_values': {
                    'property_type_name': 'Terreno',
                    'district_name': 'Cayma',
                    'land_area': 600,
                },
            }]),
            search_plan={
                'conditions': [
                    {'logical_name': 'area_max', 'value': 500},
                ],
            },
        )

        self.assertEqual(evaluation.verdict, 'replan')
        self.assertIn('SEARCH_PLAN_FILTER_MISMATCH', evaluation.signals)

    def test_replans_when_a_requirement_remains_unsatisfied(self):
        results = agent_result([])
        results['agente_propiedades']['requirements'] = [{
            'description': 'superficie menor a 500 metros',
            'satisfied': False,
        }]

        evaluation = ExecutionEvaluator.evaluate(
            message='Terrenos en Cayma con menos de 500 metros',
            results=results,
            search_plan={'conditions': []},
        )

        self.assertEqual(evaluation.verdict, 'replan')
        self.assertIn('UNSATISFIED_QUERY_REQUIREMENTS', evaluation.signals)
