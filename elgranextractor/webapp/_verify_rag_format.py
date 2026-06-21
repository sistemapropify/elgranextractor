"""
Verificar el formato RAG completo que ve el LLM.
Guarda la salida en un archivo para evitar problemas de encoding en Windows.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.services.prompts import format_rag_context, build_full_prompt, format_memory_context, format_episodic_context
from intelligence.services.rag import RAGService

output_lines = []

def log(msg=""):
    output_lines.append(str(msg))
    print(msg)

log("=== VERIFICACION DEL FORMATO RAG COMPLETO ===")
log()

# 1. Buscar documentos de ejemplo
log("1. Buscando documentos con search_dynamic...")
resultados = RAGService.search_dynamic(
    query="propiedades en venta en USD",
    collection_names=['propiedades_propify'],
    top_k=2
)

if resultados:
    log(f"   Encontrados {len(resultados)} resultados")
    log()
    
    # 2. Mostrar raw field_values del primer resultado
    log("2. Field_values del primer resultado (raw):")
    for i, r in enumerate(resultados):
        log(f"\n   --- Resultado {i+1} ---")
        fv = r.get('field_values', {})
        for k, v in sorted(fv.items()):
            log(f"   {k}: {v}")
    
    log()
    log("=" * 60)
    log()
    
    # 3. Formatear con format_rag_context
    log("3. FORMATO RAG CONTEXT (lo que ve el LLM):")
    log("=" * 60)
    rag_text = format_rag_context(resultados, detailed=True)
    log(rag_text)
    
    log()
    log("=" * 60)
    log()
    
    # 4. Simular el prompt completo
    log("4. PROMPT COMPLETO (build_full_prompt):")
    log("=" * 60)
    full_prompt = build_full_prompt(
        system_prompt="Eres un asistente inmobiliario.",
        message="¿Qué propiedades hay en venta?",
        rag_context=resultados,
        memory_context=[],
        episodic_context=[],
        detailed=True
    )
    log(full_prompt[:3000])
    
else:
    log("No se encontraron resultados de busqueda")

# Guardar a archivo
output_path = os.path.join(os.path.dirname(__file__), '_rag_format_output.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

log()
log(f"Salida completa guardada en: {output_path}")
