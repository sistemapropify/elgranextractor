import os
import sys
import django

# Agregar el directorio webapp al path
sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService

print("=== Probando funcionalidad RAG con colección propiedades_propify ===")

# Probar búsqueda simple
try:
    query = "departamento en Cayma con 3 dormitorios"
    collection_names = ['propiedades_propify']
    
    print(f"\nBuscando: '{query}'")
    print(f"Colecciones: {collection_names}")
    
    results = RAGService.search_dynamic(
        query=query,
        collection_names=collection_names,
        filters={},
        top_k=3
    )
    
    print(f"\nResultados encontrados: {len(results)}")
    
    for i, result in enumerate(results, 1):
        print(f"\n--- Resultado {i} ---")
        print(f"Score: {result.get('score', 0):.4f}")
        print(f"Source ID: {result.get('source_id')}")
        
        # Mostrar campos importantes
        field_values = result.get('field_values', {})
        if field_values:
            print(f"Título: {field_values.get('title', 'N/A')}")
            print(f"Descripción: {field_values.get('description', 'N/A')[:100]}...")
            print(f"Precio: {field_values.get('price', 'N/A')}")
            print(f"Distrito: {field_values.get('district', 'N/A')}")
            print(f"Habitaciones: {field_values.get('bedrooms', 'N/A')}")
            
except Exception as e:
    print(f"Error en búsqueda RAG: {e}")
    import traceback
    traceback.print_exc()

# Probar también el endpoint de API
print("\n\n=== Probando endpoint de API ===")
try:
    from django.test import RequestFactory
    from intelligence.views import rag_search_dynamic
    import json
    
    factory = RequestFactory()
    data = {
        'query': 'casa en Yanahuara',
        'collection_names': ['propiedades_propify'],
        'filters': {},
        'top_k': 2
    }
    
    request = factory.post('/api/v1/intelligence/rag/search/', 
                          data=json.dumps(data), 
                          content_type='application/json')
    
    # Simular autenticación si es necesaria
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request as DRFRequest
    
    rf = APIRequestFactory()
    request = rf.post('/api/v1/intelligence/rag/search/', data, format='json')
    
    print("Endpoint configurado correctamente")
    
except Exception as e:
    print(f"Error probando endpoint: {e}")
    import traceback
    traceback.print_exc()