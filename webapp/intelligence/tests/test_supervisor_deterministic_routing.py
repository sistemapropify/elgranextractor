from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.agents.supervisor import Supervisor


class DeterministicInventoryRoutingTests(SimpleTestCase):
    def _supervisor_without_init(self):
        supervisor = object.__new__(Supervisor)
        supervisor._get_agent_def = lambda name: {
            'name': name,
            'description': 'Busca inventario',
            'access_level': 1,
        }
        return supervisor

    def test_filtered_slang_query_routes_to_property_agent(self):
        supervisor = self._supervisor_without_init()

        with patch.object(
            supervisor,
            '_route_with_llm',
            side_effect=AssertionError('LLM routing should not run'),
        ):
            result = supervisor.route(
                'quiero ver depas en Cayma de 3 habitaciones y 2 baños '
                'con menos de 500 mil dólares'
            )

        self.assertEqual(result['routing_method'], 'deterministic_inventory')
        self.assertEqual(result['agents'][0]['name'], 'agente_propiedades')

    def test_explicit_client_requirement_is_not_forced_to_inventory(self):
        supervisor = self._supervisor_without_init()
        sentinel = {'routing_method': 'llm', 'agents': []}

        with patch.object(supervisor, '_route_with_llm', return_value=sentinel):
            result = supervisor.route(
                'tengo un cliente que busca depas en Cayma'
            )

        self.assertEqual(result, sentinel)

    def test_client_as_recipient_still_routes_to_property_inventory(self):
        supervisor = self._supervisor_without_init()

        with patch.object(
            supervisor,
            '_route_with_llm',
            side_effect=AssertionError('LLM routing should not run'),
        ):
            result = supervisor.route(
                'hola quiero enviarle a mi cliente departamentos '
                'en venta en Cayma'
            )

        self.assertEqual(result['routing_method'], 'deterministic_inventory')
        self.assertEqual(result['agents'][0]['name'], 'agente_propiedades')
        self.assertIn('operacion', result['reasoning'])

    def test_generic_properties_with_bedrooms_routes_without_llm(self):
        supervisor = self._supervisor_without_init()

        with patch.object(
            supervisor,
            '_route_with_llm',
            side_effect=AssertionError('LLM routing should not run'),
        ):
            result = supervisor.route(
                'muestrame propiedades con 3 habitaciones'
            )

        self.assertEqual(result['routing_method'], 'deterministic_inventory')
        self.assertEqual(result['agents'][0]['name'], 'agente_propiedades')
