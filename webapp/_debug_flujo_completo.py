import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection

# ========= PASO 1: Busqueda RAG =========
message = "que propiedades tienes en cerro colorado"
user_level = 2

print("=" * 70)
print(f"PASO 1: Busqueda RAG para: '{message}'")
print("=" * 70)

# Obtener colecciones accesibles
collections = list(IntelligenceCollection.objects.filter(
    access_level__lte=user_level,
    is_active=True
).values_list('name', flat=True))
print(f"Colecciones accesibles: {collections}")

# Hacer busqueda RAG
rag_results = RAGService.search_dynamic(
    query=message,
    collection_names=collections,
    top_k=3
)

print(f"\nResultados RAG encontrados: {len(rag_results)}")
for i, r in enumerate(rag_results):
    fv = r.get('field_values', {})
    print(f"\n  Resultado {i+1}:")
    print(f"    search_type: {r.get('search_type')}")
    print(f"    similarity: {r.get('similarity')}")
    print(f"    district_name: {fv.get('district_name', 'NO')}")
    print(f"    title: {fv.get('title', '')[:60]}")
    print(f"    price: {fv.get('price', 'N/A')}")

# ========= PASO 2: Construir prompt =========
print("\n" + "=" * 70)
print("PASO 2: Prompt que se enviaria al LLM")
print("=" * 70)

prompt_parts = []
system_instruction = """Eres el asistente inteligente de Propifai, una inmobiliaria en Arequipa, Peru.

INSTRUCCIONES OBLIGATORIAS:
1. USA SIEMPRE el contexto de "CONOCIMIENTO DEL SISTEMA (BASE DE DATOS)" cuando se te proporcione.
2. Si el usuario pregunta por propiedades en una zona especifica y el contexto contiene propiedades de esa zona, DEBES listarlas.
3. NUNCA digas "no tengo informacion" si el contexto contiene datos relevantes.
4. Si el contexto tiene propiedades, PRESENTALAS al usuario con detalles."""

prompt_parts.append(system_instruction)
prompt_parts.append("")

if rag_results:
    prompt_parts.append("=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ===")
    prompt_parts.append("Los siguientes datos provienen de la base de datos de propiedades de Propifai. Son datos REALES.")
    for i, rag in enumerate(rag_results[:5], 1):
        fv = rag.get('field_values', {})
        desc_parts = []
        title = fv.get('title', '')
        price = fv.get('price', '')
        district = fv.get('district_name', fv.get('district', ''))
        if title:
            desc_parts.append(f"Titulo: {title}")
        if price:
            desc_parts.append(f"Precio: {price}")
        if district:
            desc_parts.append(f"Distrito: {district}")
        if desc_parts:
            prompt_parts.append(f"\nPropiedad {i}:")
            for part in desc_parts:
                prompt_parts.append(f"  - {part}")
    prompt_parts.append("")
    prompt_parts.append("INSTRUCCION: Si el usuario pregunta por propiedades, USA LA INFORMACION DE ARRIBA para responder.")

prompt_parts.append("")
prompt_parts.append(f"Usuario: {message}")
prompt_parts.append("Asistente:")

full_prompt = "\n".join(prompt_parts)
print(full_prompt)

# ========= PASO 3: Verificar si el prompt tiene datos =========
print("\n" + "=" * 70)
print("PASO 3: Verificacion")
print("=" * 70)
if "Cerro Colorado" in full_prompt or "cerro colorado" in full_prompt.lower():
    print("OK: 'Cerro Colorado' aparece en el prompt")
else:
    print("ERROR: 'Cerro Colorado' NO aparece en el prompt!")
    
if "Propiedad 1" in full_prompt:
    print("OK: Hay propiedades listadas en el prompt")
else:
    print("ERROR: No hay propiedades listadas en el prompt!")
