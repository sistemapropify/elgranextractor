# -*- coding: utf-8 -*-
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from intelligence.services.prompts import format_rag_context
from intelligence.models import IntelligenceDocument
from intelligence.services.rag import RAGService

print("=" * 80)
print("TEST: Verificar formato de contexto RAG con descripción completa")
print("=" * 80)

# Obtener el documento con alcabala
try:
    doc = IntelligenceDocument.objects.get(source_id=50)
    print(f"Documento encontrado: ID={doc.id}, source_id={doc.source_id}")
    
    # Construir un resultado simulado como lo haría search_dynamic
    rag_result = {
        'document_id': str(doc.id),
        'collection_name': 'propiedades_propify',
        'source_id': doc.source_id,
        'similarity': 0.4668,
        'field_values': doc.field_values,
        'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
        'search_type': 'vector_faiss',
        'created_at': doc.created_at.isoformat() if doc.created_at else None,
    }
    
    # Formatear con detailed=True (el modo predeterminado)
    context_detailed = format_rag_context([rag_result], detailed=True)
    
    print("\n=== CONTEXTO DETALLADO ===")
    print(context_detailed)
    
    # Buscar si aparece 'alcabala' en el contexto
    if 'alcabala' in context_detailed.lower():
        print("\n✅ ¡ÉXITO! La palabra 'alcabala' aparece en el contexto detallado")
    else:
        print("\n❌ FALLIDO: La palabra 'alcabala' NO aparece en el contexto detallado")
    
    # Formatear con detailed=False
    context_simple = format_rag_context([rag_result], detailed=False)
    
    print("\n=== CONTEXTO SIMPLE ===")
    print(context_simple)
    
    if 'alcabala' in context_simple.lower():
        print("\n✅ ¡ÉXITO! La palabra 'alcabala' aparece en el contexto simple")
    else:
        print("\n❌ FALLIDO: La palabra 'alcabala' NO aparece en el contexto simple")
        
except Exception as e:
    print(f"Error al obtener documento: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETADO")
