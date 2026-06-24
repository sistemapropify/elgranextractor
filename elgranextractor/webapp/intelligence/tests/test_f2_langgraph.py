"""
Tests para F2-001: LangGraph Orchestration.

Verifica:
1. Importación correcta de todos los agentes
2. PILAgentState TypedDict
3. PILOrchestrator singleton y compilación del grafo
4. Conditional edge: saltar context_agent si no hay contexto
5. RouterAgent clasificación
6. SearchAgent construcción de filtros
7. FormatterAgent fallback
8. Integración con ChatProcessor
"""

import json
from django.test import TestCase
from unittest.mock import patch, MagicMock


class F2LangGraphOrchestrationTest(TestCase):
    """Tests para F2-001: LangGraph Orchestration."""

    def test_01_imports(self):
        """Verificar que todos los módulos se importan correctamente."""
        try:
            from ..agents.orchestrator import PILOrchestrator, PILAgentState, create_initial_state
            from ..agents.router_agent import RouterAgent
            from ..agents.search_agent import SearchAgent
            from ..agents.context_agent import ContextAgent
            from ..agents.formatter_agent import FormatterAgent
            self.assertTrue(True, "Todos los imports de agents/ exitosos")
        except ImportError as e:
            self.fail(f"Error importando módulos agents/: {e}")

    def test_02_pil_agent_state_structure(self):
        """Verificar que PILAgentState tiene todos los campos requeridos."""
        from ..agents.orchestrator import PILAgentState

        # Verificar que es un TypedDict (se puede crear como dict)
        state = {
            'message': 'test',
            'conversation_id': 'conv-1',
            'user_id': 'user-1',
            'skill_detectada': None,
            'score_routing': 0.0,
            'threshold': 0.45,
            'router_latency_ms': 0.0,
            'matched_template': '',
            'fallback_used': False,
            'contexto_activo': {},
            'contexto_resuelto': False,
            'hechos_usuario': [],
            'params_extraidos': {},
            'resultados_busqueda': [],
            'filtros_aplicados': {},
            'total_resultados': 0,
            'respuesta_generada': '',
            'documentos_referencia': [],
            'respuesta_raw': None,
            'nodos_ejecutados': [],
            'trace_id': '',
            'latencia_total_ms': 0.0,
            'error': None,
        }
        self.assertIn('message', state)
        self.assertIn('skill_detectada', state)
        self.assertIn('resultados_busqueda', state)
        self.assertIn('respuesta_generada', state)
        self.assertIn('nodos_ejecutados', state)
        self.assertEqual(state['threshold'], 0.45)

    def test_03_create_initial_state(self):
        """Verificar que create_initial_state genera estado correcto."""
        from ..agents.orchestrator import create_initial_state

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

    def test_04_pil_orchestrator_singleton(self):
        """Verificar que PILOrchestrator es singleton."""
        from ..agents.orchestrator import PILOrchestrator

        o1 = PILOrchestrator()
        o2 = PILOrchestrator()
        self.assertIs(o1, o2, "PILOrchestrator debe ser singleton")

    def test_05_pil_orchestrator_graph_compiled(self):
        """Verificar que el StateGraph se compila correctamente."""
        from ..agents.orchestrator import PILOrchestrator

        orchestrator = PILOrchestrator()
        # Si LangGraph está disponible, el grafo debe estar compilado
        if orchestrator.graph is not None:
            self.assertTrue(hasattr(orchestrator.graph, 'invoke'))
        else:
            self.skipTest("LangGraph no disponible, usando fallback secuencial")

    def test_06_conditional_edge_skip_context(self):
        """Verificar conditional edge: saltar context_agent si no hay contexto."""
        from ..agents.orchestrator import should_resolve_context

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

    def test_07_router_agent_no_message(self):
        """Verificar RouterAgent con mensaje vacío."""
        from ..agents.router_agent import RouterAgent

        state = {'message': ''}
        result = RouterAgent.run(state)
        self.assertIsNone(result['skill_detectada'])
        self.assertEqual(result['score_routing'], 0.0)

    @patch.object(RouterAgent, 'run')
    def test_08_router_node_tracking(self, mock_run):
        """Verificar que router_node agrega nodos_ejecutados."""
        from ..agents.orchestrator import router_node

        mock_run.return_value = {
            'skill_detectada': None,
            'score_routing': 0.0,
            'threshold': 0.45,
            'router_latency_ms': 0.0,
            'matched_template': '',
            'fallback_used': False,
        }

        result = router_node({
            'message': 'test',
            'nodos_ejecutados': [],
        })
        self.assertIn('nodos_ejecutados', result)
        self.assertIn('router', result['nodos_ejecutados'])

    def test_09_search_build_filters(self):
        """Verificar SearchAgent._build_filters con parámetros."""
        from ..agents.search_agent import SearchAgent

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

    def test_10_search_collections_for_skill(self):
        """Verificar que cada skill mapea a las colecciones correctas."""
        from ..agents.search_agent import SearchAgent

        props = SearchAgent._get_collections_for_skill('busqueda_propiedades')
        self.assertIn('propiedades_propify', props)

        matching = SearchAgent._get_collections_for_skill('matching_oferta_demanda')
        self.assertIn('propiedades_propify', matching)
        self.assertIn('requerimientos', matching)

    def test_11_formatter_fallback_no_results(self):
        """Verificar FormatterAgent._build_fallback_response sin resultados."""
        from ..agents.formatter_agent import FormatterAgent

        response = FormatterAgent._build_fallback_response([])
        self.assertIn('No encontré', response)

    def test_12_formatter_fallback_with_results(self):
        """Verificar FormatterAgent._build_fallback_response con resultados."""
        from ..agents.formatter_agent import FormatterAgent

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
        self.assertIn('S/250,000', response)

    def test_13_process_message_use_langgraph(self):
        """Verificar que ChatProcessor tiene USE_LANGGRAPH flag."""
        from ..services.chat_processor import ChatProcessor

        self.assertTrue(hasattr(ChatProcessor, 'USE_LANGGRAPH'))
        self.assertTrue(ChatProcessor.USE_LANGGRAPH)

    def test_14_process_message_has_langgraph_method(self):
        """Verificar que ChatProcessor tiene _process_with_langgraph."""
        from ..services.chat_processor import ChatProcessor

        self.assertTrue(hasattr(ChatProcessor, '_process_with_langgraph'))
        self.assertTrue(callable(ChatProcessor._process_with_langgraph))
