"""Regresiones para búsquedas de propiedades basadas solo en datos reales."""

from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.agents.formatter_agent import FormatterAgent
from intelligence.agents.base_agent import AgentResult
from intelligence.services.chat_processor import ChatProcessor
from intelligence.skills.propiedades.skill import BusquedaPropiedadesSkill


class PropertyFilterRegressionTests(SimpleTestCase):
    def setUp(self):
        self.skill = BusquedaPropiedadesSkill()

    def test_decimal_price_strings_are_filtered_in_python(self):
        params = {
            'distrito': 'Cayma',
            'tipo_propiedad': 'Departamento',
            'precio_max': 160000,
            'condicion': 'Disponible',
        }
        valid = {
            'district_name': 'Cayma',
            'property_type_name': 'Departamento',
            'price': '127000.0',
            'property_status_name': 'Disponible',
        }
        too_expensive = {**valid, 'price': '330000.0'}

        self.assertTrue(self.skill._doc_cumple_filtros(valid, params))
        self.assertFalse(self.skill._doc_cumple_filtros(too_expensive, params))

    def test_cercado_matches_official_arequipa_district(self):
        field_values = {
            'district_name': 'Arequipa',
            'property_type_name': 'Local Comercial',
        }

        self.assertTrue(self.skill._doc_cumple_filtros(
            field_values,
            {'distrito': 'Cercado'},
        ))
        self.assertTrue(self.skill._doc_cumple_filtros(
            field_values,
            {'distrito': 'Cercado de Arequipa'},
        ))

    def test_exact_filters_reject_unrelated_semantic_candidate(self):
        field_values = {
            'district_name': 'Yanahuara',
            'property_type_name': 'Departamento',
            'price': '120000.0',
        }
        self.assertFalse(self.skill._doc_cumple_filtros(
            field_values,
            {'distrito': 'Cayma', 'precio_max': 160000},
        ))


class FormatterGroundingRegressionTests(SimpleTestCase):
    def test_agent_result_preserves_final_answer_for_formatter(self):
        result = AgentResult(
            agent_name='agente_propiedades',
            success=True,
            final_answer=[{'document_id': '1'}],
        )

        self.assertEqual(
            result.to_log()['final_answer'],
            [{'document_id': '1'}],
        )

    @patch('intelligence.services.llm.LLMService._call_deepseek_api')
    def test_empty_property_search_never_calls_llm(self, call_llm):
        state = {
            'message': 'departamentos en Cayma por menos de 160000 dólares',
            'skill_detectada': 'busqueda_propiedades',
            'resultados_busqueda': [],
        }

        result = FormatterAgent.run(state)

        call_llm.assert_not_called()
        self.assertTrue(result['grounded_response'])
        self.assertIn('No encontré propiedades verificadas',
                      result['respuesta_generada'])

    @patch('intelligence.services.llm.LLMService._call_deepseek_api')
    def test_agent_graph_zero_results_never_calls_llm(self, call_llm):
        state = {
            'aggregated_answer': {
                'successful': [{
                    'name': 'agente_propiedades',
                    'final_answer': {'total': 0},
                }],
            },
            'results': {
                'agente_propiedades': {
                    'final_answer': {
                        'total': 0,
                        'mensaje': 'No se encontraron propiedades.',
                    },
                },
            },
        }
        ctx = type('Context', (), {
            'message': 'departamentos en Cayma',
            'conversation': None,
        })()

        response = ChatProcessor._format_agent_results(state, ctx)

        call_llm.assert_not_called()
        self.assertIn('No encontré propiedades verificadas', response)

    @patch('intelligence.services.llm.LLMService._call_deepseek_api')
    def test_agent_graph_lists_every_real_property_without_llm(self, call_llm):
        properties = [
            {
                'document_id': str(index),
                'field_values': {
                    'title': f'Departamento real {index}',
                    'price': 150000 + index,
                    'currency_name': 'Dolares',
                    'district_name': 'Cayma',
                    'property_type_name': 'Departamento',
                },
            }
            for index in range(1, 9)
        ]
        state = {
            'aggregated_answer': {
                'successful': [{'name': 'agente_propiedades'}],
            },
            'results': {
                'agente_propiedades': {
                    'success': True,
                    'final_answer': properties,
                    'iterations_used': 1,
                    'confidence': 1.0,
                    'steps': [],
                },
            },
        }
        ctx = type('Context', (), {
            'message': 'departamentos en Cayma de más de 150000 dólares',
            'conversation': None,
        })()

        response = ChatProcessor._format_agent_results(state, ctx)

        call_llm.assert_not_called()
        self.assertIn('**8 propiedades**', response)
        for index in range(1, 9):
            self.assertIn(f'Departamento real {index}', response)
