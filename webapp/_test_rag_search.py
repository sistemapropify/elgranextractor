"""
Test: Verificar que la búsqueda RAG funciona y el prompt anti-alucinación está activo.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.services.rag import RAGService
from intelligence.services.prompts import format_rag_context, build_full_prompt, PromptManager

# 1. Probar búsqueda RAG con datos reales
print('=== 1. BÚSQUEDA RAG: "propiedades en Cayma" ===')
results = RAGService.search_dynamic(
    query="propiedades en Cayma",
    collection_names=['propiedades_propify'],
    top_k=3
)
print(f'  Resultados encontrados: {len(results)}')
for r in results:
    fv = r.get('field_values', {})
    print(f'  - {fv.get("title", "N/A")} | Precio: {fv.get("price", "N/A")} | Distrito: {fv.get("district", "N/A")}')

# 2. Probar búsqueda sin resultados (debería activar anti-alucinación)
print('\n=== 2. BÚSQUEDA RAG: "propiedades en Marte" (sin resultados) ===')
results_empty = RAGService.search_dynamic(
    query="propiedades en Marte",
    collection_names=['propiedades_propify'],
    top_k=3
)
print(f'  Resultados encontrados: {len(results_empty)}')

# 3. Probar format_rag_context con datos
print('\n=== 3. FORMAT_RAG_CONTEXT CON DATOS ===')
context_with_data = format_rag_context(results, detailed=True)
print(context_with_data[:500])
print('...')

# 4. Probar format_rag_context SIN datos (debería decir NO HAY DATOS DISPONIBLES)
print('\n=== 4. FORMAT_RAG_CONTEXT SIN DATOS ===')
context_empty = format_rag_context([], detailed=True)
print(context_empty)

# 5. Verificar que el system prompt tiene instrucciones anti-alucinación
print('\n=== 5. SYSTEM PROMPTS ===')
sys_prompt = PromptManager.get_system_prompt('chat-web')
print(f'DEFAULT_SYSTEM_PROMPT tiene "NO INVENTES DATOS": {"NO INVENTES DATOS" in sys_prompt}')
print(f'DEFAULT_SYSTEM_PROMPT tiene "NO HAY DATOS DISPONIBLES": {"NO HAY DATOS DISPONIBLES" in sys_prompt}')

deepseek_prompt = PromptManager.get_deepseek_system_prompt('chat-web')
print(f'DEFAULT_DEEPSEEK_SYSTEM_PROMPT tiene "NUNCA inventes": {"NUNCA inventes" in deepseek_prompt}')
print(f'DEFAULT_DEEPSEEK_SYSTEM_PROMPT tiene "NO HAY DATOS DISPONIBLES": {"NO HAY DATOS DISPONIBLES" in deepseek_prompt}')

print('\n=== HECHO ===')
