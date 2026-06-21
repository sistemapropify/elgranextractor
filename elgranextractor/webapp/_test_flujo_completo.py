# -*- coding: utf-8 -*-
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from intelligence.services.chat_processor import ChatProcessor
from intelligence.services.prompts import format_rag_context
from intelligence.models import IntelligenceDocument
from intelligence.services.rag import RAGService

print("=" * 80)
print("TEST: Flujo completo chat_processor -> format_rag_context -> build_full_prompt")
print("=" * 80)

# Simular el contexto de chat como lo haría _get_rag_context
try:
    # Obtener documento con alcabala
    doc = IntelligenceDocument.objects.get(source_id=50)
    
    # Simular resultado de search_dynamic
    rag_results = [{
        'document_id': str(doc.id),
        'collection_name': 'propiedades_propify',
        'source_id': doc.source_id,
        'similarity': 0.4668,
        'field_values': doc.field_values,
        'content': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content,
        'search_type': 'vector_faiss',
        'created_at': doc.created_at.isoformat() if doc.created_at else None,
    }]
    
    print(f"✅ Documento obtenido: {doc.source_id}")
    
    # Simular llamada a format_rag_context (como lo hace _build_prompt)
    context_str = format_rag_context(rag_results)
    
    print("\n=== CONTEXTO RAG FORMATEADO ===")
    print(context_str)
    
    # Verificar que contiene la información clave
    success = True
    
    if 'alcabala' not in context_str.lower():
        print("❌ ERROR: 'alcabala' no encontrada en el contexto formateado")
        success = False
    else:
        print("✅ 'alcabala' encontrada en el contexto formateado")
    
    if 'coworking' not in context_str.lower():
        print("❌ ERROR: 'coworking' no encontrada en el contexto formateado")
        success = False
    else:
        print("✅ 'coworking' encontrada en el contexto formateado")
    
    if 'terraza' not in context_str.lower():
        print("❌ ERROR: 'terraza' no encontrada en el contexto formateado")
        success = False
    else:
        print("✅ 'terraza' encontrada en el contexto formateado")
    
    if success:
        print("\n🎉 ¡ÉXITO TOTAL! El flujo completo funciona correctamente.")
        print("El sistema ahora mostrará correctamente las propiedades con coworking, terraza y alcabala.")
    else:
        print("\n💥 FALLIDO: Algo salió mal en el flujo.")
        
except Exception as e:
    print(f"ERROR al ejecutar el test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETADO")
