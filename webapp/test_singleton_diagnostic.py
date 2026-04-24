#!/usr/bin/env python
"""
Diagnóstico del singleton de embeddings para identificar por qué se inicializa en cada llamada.
"""
import os
import sys
import time
import logging

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from intelligence.services.rag import RAGService
from intelligence.services.llm import LLMService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_singleton_initialization():
    """Test para verificar si el singleton se inicializa una sola vez."""
    print("=== TEST DE SINGLETON DE EMBEDDINGS ===")
    print()
    
    # Test 1: Llamadas directas a RAGService
    print("Test 1: Llamadas directas a RAGService.generate_embedding")
    print("-" * 50)
    
    start_time = time.time()
    embedding1 = RAGService.generate_embedding("Test de embeddings")
    time1 = time.time() - start_time
    print(f"Primera llamada: {time1:.2f} segundos")
    
    start_time = time.time()
    embedding2 = RAGService.generate_embedding("Otra consulta de test")
    time2 = time.time() - start_time
    print(f"Segunda llamada: {time2:.2f} segundos")
    
    start_time = time.time()
    embedding3 = RAGService.generate_embedding("Tercera consulta")
    time3 = time.time() - start_time
    print(f"Tercera llamada: {time3:.2f} segundos")
    
    print(f"Embedding 1 generado: {len(embedding1) if embedding1 else 0} bytes")
    print(f"Embedding 2 generado: {len(embedding2) if embedding2 else 0} bytes")
    print(f"Embedding 3 generado: {len(embedding3) if embedding3 else 0} bytes")
    print()
    
    # Test 2: Llamadas a LLMService.generate_rag_response
    print("Test 2: Llamadas a LLMService.generate_rag_response")
    print("-" * 50)
    
    # Primera llamada
    start_time = time.time()
    success1, message1, response1 = LLMService.generate_rag_response(
        query="Propiedades en Cayma",
        user_access_level=3
    )
    time4 = time.time() - start_time
    print(f"Primera llamada LLMService: {time4:.2f} segundos")
    print(f"Éxito: {success1}, Mensaje: {message1[:50]}...")
    
    # Segunda llamada
    start_time = time.time()
    success2, message2, response2 = LLMService.generate_rag_response(
        query="Casas en Yanahuara",
        user_access_level=3
    )
    time5 = time.time() - start_time
    print(f"Segunda llamada LLMService: {time5:.2f} segundos")
    print(f"Éxito: {success2}, Mensaje: {message2[:50]}...")
    
    print()
    
    # Test 3: Verificar estado del singleton
    print("Test 3: Estado del singleton")
    print("-" * 50)
    print(f"RAGService._embedder es None: {RAGService._embedder is None}")
    
    if RAGService._embedder is not None:
        print(f"Modelo cargado: {RAGService._embedder.__class__.__name__}")
        print(f"Dimensiones: {RAGService.EMBEDDING_DIMENSIONS}")
    
    # Test 4: Llamadas concurrentes simuladas
    print()
    print("Test 4: Llamadas rápidas consecutivas")
    print("-" * 50)
    
    queries = [
        "Departamentos en Miraflores",
        "Terrenos en Cerro Colorado",
        "Locales comerciales en Cercado",
        "Oficinas en Paucarpata"
    ]
    
    times = []
    for i, query in enumerate(queries, 1):
        start_time = time.time()
        embedding = RAGService.generate_embedding(query)
        elapsed = time.time() - start_time
        times.append(elapsed)
        print(f"Consulta {i} ('{query}'): {elapsed:.3f} segundos")
    
    print(f"\nTiempo promedio: {sum(times)/len(times):.3f} segundos")
    print(f"Tiempo máximo: {max(times):.3f} segundos")
    print(f"Tiempo mínimo: {min(times):.3f} segundos")
    
    print()
    print("=== ANÁLISIS ===")
    print()
    
    # Análisis de resultados
    if time1 > 2.0 and time2 < 0.5 and time3 < 0.5:
        print("✓ Singleton funciona correctamente:")
        print("  - Primera llamada lenta (carga del modelo)")
        print("  - Llamadas subsiguientes rápidas (modelo en caché)")
    elif time1 > 2.0 and time2 > 2.0 and time3 > 2.0:
        print("✗ Singleton NO funciona: modelo se carga en cada llamada")
        print("  Posibles causas:")
        print("  1. El singleton se está reinicializando")
        print("  2. Hay múltiples instancias de la clase")
        print("  3. El modelo se descarga después de cada uso")
    else:
        print("⚠ Comportamiento mixto: necesita investigación adicional")
    
    # Verificar tiempos de LLMService
    if time4 > 10.0:
        print(f"\n⚠ LLMService lento ({time4:.1f} segundos)")
        print("  Posibles causas:")
        print("  1. Inicialización de embeddings en cada llamada")
        print("  2. Llamada a DeepSeek API lenta")
        print("  3. Búsqueda RAG ineficiente")
    
    print()
    print("=== RECOMENDACIONES ===")
    print()
    
    if RAGService._embedder is None:
        print("1. El modelo de embeddings NO está cargado en memoria")
        print("   - Implementar pre-carga al iniciar la aplicación")
    else:
        print("1. El modelo de embeddings está cargado en memoria")
        print("   - Verificar que no se reinicialice")
    
    print("2. Considerar implementar caché de embeddings de consultas")
    print("   - Usar LRU cache para queries frecuentes")
    print("3. Optimizar búsqueda RAG:")
    print("   - Usar índices vectoriales si hay muchos documentos")
    print("   - Implementar paginación para resultados")
    
    return {
        "rag_times": [time1, time2, time3],
        "llm_times": [time4, time5],
        "consecutive_times": times,
        "embedder_loaded": RAGService._embedder is not None
    }

if __name__ == "__main__":
    results = test_singleton_initialization()
    
    # Guardar resultados para análisis
    import json
    with open("singleton_diagnostic_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nResultados guardados en singleton_diagnostic_results.json")