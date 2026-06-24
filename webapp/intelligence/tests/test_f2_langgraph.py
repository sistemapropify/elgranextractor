"""
Tests para F2-001: LangGraph Orchestration.

Verifica:
1. Importación correcta de todos los agentes
2. PILAgentState TypedDict
3. Conditional edge: saltar context_agent si no hay contexto
4. RouterAgent clasificación
5. SearchAgent construcción de filtros
6. FormatterAgent fallback
7. ChatProcessor flag LangGraph
"""

from django.test import TestCase
from unittest.mock import patch


class F2LangGraphOrchestrationTest(TestCase):
    """Tests para F2-001: LangGraph Orchestration."""

    def test_01_imports(self):
        """Verificar que todos los módulos se importan correctamente."""
        try:
            from intelligence.agents.orchestrator import PILOrchestrator, PILAgentState, create_initial_state
            from intelligence.agents.router_agent import RouterAgent
            from intelligence.agents.search_agent import SearchAgent
            from intelligence.agents.context_agent import ContextAgent
            from intelligence.agents.formatter_agent import FormatterAgent
            self.assertTrue(True, "Todos los imports de agents/ exitosos")
        except ImportError as e:
            self.fail(f"Error importando módulos agents/: {e}")

    def test_02_create_initial_state(self):
        """Verificar que create_initial_state genera estado correcto."""
        from intelligence.agents.orchestrator import create_initial_state

        state = create_initial_state(
            message="busco departamento en Cayma",
            conversation_id="conv-123",
            user_id="user-456",
            contexto_activo={"distrito": "Cayma"},
        )

        self.assertEqual(state['message'], "busco departamento en Cayma")
        self.assertEqual(state['conversation_id'], "conv-123")
        self.assertEqual(state['user_id'], "user-456")
        self.assertEqual(state['contexto_activo'], {"distrito": "Cayma"})
        self.assertEqual(state['threshold'], 0.45)
        self.assertIsNotNone(state['trace_id'])
        self.assertEqual(len(state['trace_id']), 12)

    def test_03_conditional_edge_skip_context(self):
        """Verificar conditional edge: saltar context_agent si no hay contexto."""
        from intelligence.agents.orchestrator import should_resolve_context

        # Sin contexto activo → debe saltar a search
        state_no_context = {
            'contexto_activo': {},
            'message': 'hola',
        }
        result = should_resolve_context(state_no_context)
        self.assertEqual(result, 'search')

        # Con contexto activo → debe ir a context_resolver
        state_with_context = {
            'contexto_activo': {'distrito': 'Cayma'},
            'message': 'muéstrame más',
        }
        result = should_resolve_context(state_with_context)
        self.assertEqual(result, 'context_resolver')

    def test_04_router_agent_no_message(self):
        """Verificar RouterAgent con mensaje vacío."""
        from intelligence.agents.router_agent import RouterAgent

        state = {'message': ''}
        result = RouterAgent.run(state)
        self.assertIsNone(result['skill_detectada'])
        self.assertEqual(result['score_routing'], 0.0)

    def test_05_search_build_filters(self):
        """Verificar SearchAgent._build_filters con parámetros."""
        from intelligence.agents.search_agent import SearchAgent

        # Sin parámetros
        filters = SearchAgent._build_filters({}, 'busqueda_propiedades')
        self.assertEqual(filters, {})

        # Con parámetros
        filters = SearchAgent._build_filters(
            {'distrito': 'Cayma', 'tipo_propiedad': 'Departamento'},
            'busqueda_propiedades'
        )
        self.assertEqual(filters.get('distrito'), 'Cayma')
        self.assertEqual(filters.get('tipo_propiedad'), 'Departamento')

    def test_06_search_collections_for_skill(self):
        """Verificar que cada skill mapea a las colecciones correctas."""
        from intelligence.agents.search_agent import SearchAgent

        props = SearchAgent._get_collections_for_skill('busqueda_propiedades')
        self.assertIn('propiedades_propify', props)

    def test_07_formatter_fallback_no_results(self):
        """Verificar FormatterAgent._build_fallback_response sin resultados."""
        from intelligence.agents.formatter_agent import FormatterAgent

        response = FormatterAgent._build_fallback_response([])
        self.assertIn('No encontré', response)

    def test_08_formatter_fallback_with_results(self):
        """Verificar FormatterAgent._build_fallback_response con resultados."""
        from intelligence.agents.formatter_agent import FormatterAgent

        resultados = [
            {
                'field_values': {
                    'titulo': 'Departamento en Cayma',
                    'precio': 'S/250,000',
                    'distrito': 'Cayma',
                }
            }
        ]
        response = FormatterAgent._build_fallback_response(resultados)
        self.assertIn('Departamento en Cayma', response)

    def test_09_chatprocessor_has_langgraph_flag(self):
        """Verificar que ChatProcessor tiene USE_LANGGRAPH flag."""
        from intelligence.services.chat_processor import ChatProcessor

        self.assertTrue(hasattr(ChatProcessor, 'USE_LANGGRAPH'))
        self.assertTrue(ChatProcessor.USE_LANGGRAPH)

    def test_10_chatprocessor_has_langgraph_method(self):
        """Verificar que ChatProcessor tiene _process_with_langgraph."""
        from intelligence.services.chat_processor import ChatProcessor

        self.assertTrue(hasattr(ChatProcessor, '_process_with_langgraph'))
        self.assertTrue(callable(ChatProcessor._process_with_langgraph))
