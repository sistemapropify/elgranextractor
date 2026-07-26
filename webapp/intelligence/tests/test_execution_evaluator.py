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
    def test_replans_inventory_query_routed_to_crm(self):
        evaluation = ExecutionEvaluator.evaluate(
            message=(
                'quiero enviarle a mi cliente departamentos '
                'en venta en Cayma'
            ),
            results={
                'agente_requerimientos': {
                    'success': True,
                    'final_answer': {'data': [{'client_name': 'Carlos'}]},
                    'requirements': [{
                        'description': 'Obtener departamentos en Cayma',
                        'satisfied': True,
                    }],
                    'steps': [{
                        'skill_used': 'mis_requerimientos',
                        'skill_success': True,
                    }],
                },
            },
            search_plan={
                'conditions': [
                    {'logical_name': 'distrito', 'value': 'Cayma'},
                    {
                        'logical_name': 'tipo_propiedad',
                        'value': 'Departamento',
                    },
                    {'logical_name': 'operacion', 'value': 'Venta'},
                ],
            },
        )

        self.assertEqual(evaluation.verdict, 'replan')
        self.assertEqual(evaluation.suggested_agent, 'agente_propiedades')
        self.assertIn('WRONG_AGENT_SELECTED', evaluation.signals)
        self.assertIn('WRONG_SKILL_FOR_REQUIREMENT', evaluation.signals)
        self.assertIn('EVIDENCE_DOMAIN_MISMATCH', evaluation.signals)

    def test_blocks_persistent_inventory_domain_mismatch(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='muestrame departamentos en Cayma',
            results={
                'agente_requerimientos': {
                    'success': True,
                    'final_answer': {'data': [{'client_name': 'Carlos'}]},
                    'requirements': [],
                    'steps': [{'skill_used': 'mis_requerimientos'}],
                },
            },
            search_plan={'conditions': []},
            attempt=1,
        )

        self.assertEqual(evaluation.verdict, 'block')
        self.assertIn(
            'REPLAN_DID_NOT_FIX_DOMAIN_MISMATCH',
            evaluation.signals,
        )

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

    def test_groups_broad_inventory_when_query_has_explicit_filter(self):
        items = [
            {'source_id': index, 'field_values': {'bedrooms': 3}}
            for index in range(51)
        ]
        evaluation = ExecutionEvaluator.evaluate(
            message='Muéstrame propiedades con 3 habitaciones',
            results=agent_result(items),
            search_plan={
                'conditions': [{
                    'logical_name': 'habitaciones',
                    'value': 3,
                }],
            },
        )
        self.assertEqual(evaluation.verdict, 'pass')
        self.assertIn('BROAD_RESULTS_GROUPED', evaluation.signals)

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

    def test_replans_when_exact_bedrooms_result_has_more_rooms(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Propiedades con 3 habitaciones',
            results=agent_result([{
                'source_id': 1,
                'field_values': {'bedrooms': 5},
            }]),
            search_plan={
                'conditions': [{
                    'logical_name': 'habitaciones',
                    'value': 3,
                }],
            },
        )
        self.assertEqual(evaluation.verdict, 'replan')
        self.assertIn('SEARCH_PLAN_FILTER_MISMATCH', evaluation.signals)
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

    def test_terrain_area_max_uses_total_area_fallback(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Terrenos de menos de 500 metros',
            results=agent_result([{
                'source_id': 1,
                'field_values': {
                    'property_type_name': 'Terreno',
                    'total_area': 450,
                },
            }]),
            search_plan={
                'conditions': [
                    {'logical_name': 'tipo_propiedad', 'value': 'Terreno'},
                    {'logical_name': 'area_max', 'value': 500},
                ],
            },
        )
        self.assertEqual(evaluation.verdict, 'pass')

    def test_terrain_area_max_rejects_large_land_area_even_if_built_is_small(self):
        evaluation = ExecutionEvaluator.evaluate(
            message='Terrenos de menos de 500 metros',
            results=agent_result([{
                'source_id': 1,
                'field_values': {
                    'property_type_name': 'Terreno',
                    'land_area': 700,
                    'built_area': 100,
                },
            }]),
            search_plan={
                'conditions': [
                    {'logical_name': 'tipo_propiedad', 'value': 'Terreno'},
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
