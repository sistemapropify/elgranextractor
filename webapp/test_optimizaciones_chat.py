#!/usr/bin/env python
"""
Test de optimizaciones del chat - Verifica que las mejoras de rendimiento funcionen.
"""
import os
import sys
import time
import json
import logging

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from intelligence.services.rag import RAGService
from intelligence.services.llm import LLMService
from intelligence.services.memory import MemoryService
from intelligence.models import User, Conversation, Fact
import uuid

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_singleton_performance():
    """Test de rendimiento del singleton de embeddings."""
    print("=== TEST DE SINGLETON Y CACHÉ ===")
    print()
    
    # 1. Estado inicial
    print("1. Estado inicial del singleton:")
    initial_status = RAGService.get_embedder_status()
    print(f"   - Modelo cargado: {initial_status['loaded']}")
    print(f"   - Tamaño de caché: {initial_status['cache_size']}")
    print(f"   - Hits de caché: {initial_status.get('cache_hits', 0)}")
    print(f"   - Misses de caché: {initial_status.get('cache_misses', 0)}")
    print()
    
    # 2. Test de embeddings con caché
    print("2. Test de embeddings con caché:")
    test_queries = [
        "Propiedades en Cayma para venta",
        "Departamentos en Yanahuara con 3 dormitorios",
        "Casas en Miraflores con jardín",
        "Terrenos en Cerro Colorado urbanizados",
        "Locales comerciales en Cercado Arequipa"
    ]
    
    # Primera ronda (debería ser lenta - misses)
    print("   - Primera ronda (misses de caché):")
    first_times = []
    for i, query in enumerate(test_queries, 1):
        start = time.time()
        embedding = RAGService.generate_embedding(query, use_cache=True)
        elapsed = time.time() - start
        first_times.append(elapsed)
        print(f"     {i}. '{query[:30]}...' - {elapsed:.3f}s - {len(embedding) if embedding else 0} bytes")
    
    # Segunda ronda (debería ser rápida - hits)
    print("   - Segunda ronda (hits de caché):")
    second_times = []
    for i, query in enumerate(test_queries, 1):
        start = time.time()
        embedding = RAGService.generate_embedding(query, use_cache=True)
        elapsed = time.time() - start
        second_times.append(elapsed)
        print(f"     {i}. '{query[:30]}...' - {elapsed:.3f}s - {len(embedding) if embedding else 0} bytes")
    
    # Estadísticas
    avg_first = sum(first_times) / len(first_times)
    avg_second = sum(second_times) / len(second_times)
    speedup = avg_first / avg_second if avg_second > 0 else 0
    
    print(f"   - Estadísticas:")
    print(f"     • Promedio primera ronda: {avg_first:.3f}s")
    print(f"     • Promedio segunda ronda: {avg_second:.3f}s")
    print(f"     • Aceleración: {speedup:.1f}x")
    
    if speedup > 5:
        print("     ✓ Caché funcionando correctamente")
    else:
        print("     ⚠ Caché con aceleración limitada")
    print()
    
    # 3. Test de búsqueda RAG
    print("3. Test de búsqueda RAG:")
    query = "Propiedades en Cayma"
    start = time.time()
    success, message, results = RAGService.search(
        query=query,
        access_level=3,
        limit=5
    )
    rag_time = time.time() - start
    
    print(f"   - Query: '{query}'")
    print(f"   - Tiempo: {rag_time:.2f}s")
    print(f"   - Éxito: {success}")
    print(f"   - Resultados: {len(results)}")
    print()
    
    # 4. Test de LLM con contexto
    print("4. Test de LLM con contexto:")
    
    # Crear usuario de prueba
    user_id = uuid.uuid4()
    test_user, created = User.objects.get_or_create(
        id=user_id,
        defaults={
            'name': 'Test User',
            'email': 'test@example.com',
            'phone': '999999999'
        }
    )
    
    # Agregar algunos hechos
    facts = [
        ("usuario", "trabaja_en", "área de sistemas", 1.0),
        ("usuario", "vive_en", "Yanahuara, Arequipa", 0.9),
        ("usuario", "busca", "departamento en Cayma", 0.8),
    ]
    
    for subject, relation, obj, confidence in facts:
        Fact.objects.create(
            user=test_user,
            subject=subject,
            relation=relation,
            object=obj,
            confidence_score=confidence,
            source='test'
        )
    
    # Test de memoria
    memory_service = MemoryService(user_id=str(user_id))
    context = memory_service.get_relevant_context("¿En qué área trabajo?", limit=3)
    
    print(f"   - Hechos creados: {len(facts)}")
    print(f"   - Contexto relevante encontrado: {len(context)} hechos")
    
    for i, fact in enumerate(context, 1):
        print(f"     {i}. {fact['subject']} {fact['relation']} {fact['object']} (conf: {fact['confidence_score']:.2f})")
    print()
    
    # 5. Test de respuesta completa del chat
    print("5. Test de respuesta completa del chat:")
    
    conversation_history = [
        {"role": "user", "content": "Hola, ¿qué propiedades tienes en Cayma?"},
        {"role": "assistant", "content": "Te muestro propiedades disponibles en Cayma..."}
    ]
    
    start = time.time()
    success, message, response = LLMService.generate_rag_response(
        query="Necesito un departamento de 3 dormitorios",
        conversation_history=conversation_history,
        user_access_level=3
    )
    llm_time = time.time() - start
    
    print(f"   - Tiempo total: {llm_time:.2f}s")
    print(f"   - Éxito: {success}")
    print(f"   - Longitud respuesta: {len(response.get('response', ''))} caracteres")
    print(f"   - Fragmento: {response.get('response', '')[:100]}...")
    print()
    
    # 6. Estado final
    print("6. Estado final del sistema:")
    final_status = RAGService.get_embedder_status()
    
    print(f"   - Modelo cargado: {final_status['loaded']}")
    print(f"   - Tamaño de caché: {final_status['cache_size']}")
    print(f"   - Hits de caché: {final_status.get('cache_hits', 0)}")
    print(f"   - Misses de caché: {final_status.get('cache_misses', 0)}")
    print(f"   - Hit rate: {(final_status.get('cache_hits', 0) / (final_status.get('cache_hits', 0) + final_status.get('cache_misses', 1)) * 100):.1f}%")
    print()
    
    # 7. Análisis de resultados
    print("=== ANÁLISIS DE RESULTADOS ===")
    print()
    
    # Verificar singleton
    if final_status['loaded']:
        print("✓ Singleton funcionando correctamente")
    else:
        print("✗ Singleton NO funcionando - modelo no cargado")
    
    # Verificar caché
    cache_hits = final_status.get('cache_hits', 0)
    cache_misses = final_status.get('cache_misses', 0)
    
    if cache_hits > 0 and cache_misses > 0:
        hit_rate = cache_hits / (cache_hits + cache_misses)
        if hit_rate > 0.3:  # Al menos 30% de hits
            print(f"✓ Caché funcionando (hit rate: {hit_rate*100:.1f}%)")
        else:
            print(f"⚠ Caché con bajo hit rate ({hit_rate*100:.1f}%)")
    else:
        print("⚠ Caché no probada suficientemente")
    
    # Verificar rendimiento
    if llm_time < 10.0:
        print(f"✓ Rendimiento aceptable ({llm_time:.1f}s por respuesta)")
    elif llm_time < 20.0:
        print(f"⚠ Rendimiento moderado ({llm_time:.1f}s por respuesta)")
    else:
        print(f"✗ Rendimiento pobre ({llm_time:.1f}s por respuesta)")
    
    # Verificar aceleración de caché
    if speedup > 5:
        print(f"✓ Caché efectiva ({speedup:.1f}x más rápido)")
    elif speedup > 2:
        print(f"⚠ Caché moderadamente efectiva ({speedup:.1f}x más rápido)")
    else:
        print(f"✗ Caché no efectiva ({speedup:.1f}x más rápido)")
    
    print()
    print("=== RECOMENDACIONES ===")
    print()
    
    if llm_time > 15.0:
        print("1. El tiempo de respuesta del chat es alto (>15s)")
        print("   - Considerar optimizar la búsqueda RAG")
        print("   - Revisar conexión con DeepSeek API")
        print("   - Implementar paginación para documentos RAG")
    
    if speedup < 3:
        print("2. La caché no es suficientemente efectiva")
        print("   - Aumentar tamaño de caché (RAG_EMBEDDING_CACHE_SIZE)")
        print("   - Pre-cargar consultas frecuentes al iniciar")
        print("   - Considerar usar caché distribuida (Redis)")
    
    if not final_status['loaded']:
        print("3. El modelo de embeddings no está cargado")
        print("   - Verificar instalación de sentence-transformers")
        print("   - Ejecutar: pip install sentence-transformers")
        print("   - Ejecutar comando: python manage.py preload_embeddings")
    
    print()
    print("=== RESUMEN ===")
    print(f"- Tiempo promedio embeddings (sin caché): {avg_first:.3f}s")
    print(f"- Tiempo promedio embeddings (con caché): {avg_second:.3f}s")
    print(f"- Aceleración caché: {speedup:.1f}x")
    print(f"- Tiempo búsqueda RAG: {rag_time:.2f}s")
    print(f"- Tiempo respuesta LLM: {llm_time:.2f}s")
    print(f"- Hit rate caché: {(cache_hits/(cache_hits+cache_misses)*100 if (cache_hits+cache_misses)>0 else 0):.1f}%")
    
    return {
        'singleton_loaded': final_status['loaded'],
        'cache_size': final_status['cache_size'],
        'cache_hits': cache_hits,
        'cache_misses': cache_misses,
        'cache_hit_rate': cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0,
        'embedding_times_first': first_times,
        'embedding_times_second': second_times,
        'embedding_speedup': speedup,
        'rag_search_time': rag_time,
        'llm_response_time': llm_time,
        'overall_performance': 'good' if llm_time < 10.0 else 'moderate' if llm_time < 20.0 else 'poor'
    }

if __name__ == "__main__":
    print("Iniciando test de optimizaciones del chat...")
    print("=" * 60)
    
    try:
        results = test_singleton_performance()
        
        # Guardar resultados
        with open("optimizaciones_chat_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print()
        print("Resultados guardados en optimizaciones_chat_results.json")
        
    except Exception as e:
        print(f"Error durante el test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)