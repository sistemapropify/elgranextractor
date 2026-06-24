"""
Quick test script for F2-001 LangGraph Orchestration.
Run with: python manage.py run_langgraph_tests
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

results = []
PASS = "[PASS]"
FAIL = "[FAIL]"

def test(name, condition):
    status = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  {status} {name}")

print("\n=== F2-001 LangGraph Orchestration Tests ===\n")

print("1. Imports...")
from intelligence.agents.orchestrator import PILOrchestrator, create_initial_state, should_resolve_context
from intelligence.agents.router_agent import RouterAgent
from intelligence.agents.search_agent import SearchAgent
from intelligence.agents.formatter_agent import FormatterAgent
test("All agent imports", True)

print("\n2. State management...")
state = create_initial_state(message="busco departamento en Cayma", conversation_id="conv-1", user_id="user-1")
test("create_initial_state message", state['message'] == "busco departamento en Cayma")
test("threshold=0.45", state['threshold'] == 0.45)
test("trace_id generated", len(state['trace_id']) == 12)

print("\n3. Conditional edge...")
test("skip context if no context", should_resolve_context({'contexto_activo': {}}) == 'search')
test("run context if has context", should_resolve_context({'contexto_activo': {'d': 'Cayma'}}) == 'context_resolver')

print("\n4. RouterAgent...")
result = RouterAgent.run({'message': ''})
test("empty message returns None skill", result['skill_detectada'] is None)
test("empty message score=0", result['score_routing'] == 0.0)

print("\n5. SearchAgent...")
filters = SearchAgent._build_filters({'distrito': 'Cayma'}, 'busqueda_propiedades')
test("build_filters distrito", filters.get('distrito') == 'Cayma')
test("empty filters returns {}", SearchAgent._build_filters({}, 'bp') == {})
cols = SearchAgent._get_collections_for_skill('busqueda_propiedades')
test("collection for busqueda", 'propiedades_propify' in cols)

print("\n6. FormatterAgent...")
test("fallback no results", 'No encontre' in FormatterAgent._build_fallback_response([]) or 'No encontr' in FormatterAgent._build_fallback_response([]))
test("fallback with results", 'Test' in FormatterAgent._build_fallback_response([{'field_values': {'titulo': 'Test'}}]))

print("\n7. PILOrchestrator...")
orch = PILOrchestrator()
test("orchestrator singleton", PILOrchestrator() is orch)
test("graph compiled", orch.graph is not None)

print("\n8. ChatProcessor...")
from intelligence.services.chat_processor import ChatProcessor
test("USE_LANGGRAPH flag", ChatProcessor.USE_LANGGRAPH == True)
test("_process_with_langgraph exists", hasattr(ChatProcessor, '_process_with_langgraph'))

print("\n" + "="*50)
passed = sum(1 for r in results if r[1])
total = len(results)
print(f"RESULTADOS: {passed}/{total} tests pasaron")
if passed == total:
    print("TODOS LOS TESTS PASARON!")
else:
    print(f"{total-passed} tests fallaron")
