"""
Script de prueba para verificar la implementación del sistema RAG (SPEC-003).

Este script prueba los componentes principales del sistema RAG según
los criterios de éxito definidos en SPEC-003.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from intelligence.services.rag import RAGService
from intelligence.services.llm import LLMService
from django.db import connection


def test_criterion_1_models():
    """Prueba 1: Modelos de base de datos creados."""
    print("\n=== PRUEBA 1: Modelos de base de datos ===")
    
    try:
        # Verificar que los modelos existen
        collections_count = IntelligenceCollection.objects.count()
        documents_count = IntelligenceDocument.objects.count()
        
        print(f"✓ Modelos importados correctamente")
        print(f"  - IntelligenceCollection: {collections_count} registros")
        print(f"  - IntelligenceDocument: {documents_count} registros")
        
        # Verificar estructura de la tabla
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'intelligence_intelligencecollection'
            """)
            columns = cursor.fetchall()
            print(f"  - Columnas en IntelligenceCollection: {len(columns)}")
            
        return True
        
    except Exception as e:
        print(f"✗ Error en prueba de modelos: {e}")
        return False


def test_criterion_2_rag_service():
    """Prueba 2: Servicio RAG implementado."""
    print("\n=== PRUEBA 2: Servicio RAG ===")
    
    try:
        # Verificar que la clase existe y tiene métodos requeridos
        required_methods = [
            'initialize_embedder',
            'generate_embedding', 
            'create_collection',
            'sync_collection',
            'search',
            'delete_collection',
            'initialize_default_collections'
        ]
        
        for method in required_methods:
            if hasattr(RAGService, method):
                print(f"✓ Método '{method}' presente")
            else:
                print(f"✗ Método '{method}' faltante")
                return False
        
        # Verificar configuración
        print(f"✓ Modelo de embeddings: {RAGService.EMBEDDING_MODEL}")
        print(f"✓ Dimensiones: {RAGService.EMBEDDING_DIMENSIONS}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error en prueba de servicio RAG: {e}")
        return False


def test_criterion_3_sync_command():
    """Prueba 3: Comando de sincronización automática."""
    print("\n=== PRUEBA 3: Comando de sincronización ===")
    
    try:
        # Verificar que el archivo del comando existe
        command_path = os.path.join(
            os.path.dirname(__file__),
            'intelligence', 'management', 'commands', 'sincronizar_rag.py'
        )
        
        if os.path.exists(command_path):
            print(f"✓ Archivo del comando encontrado: {command_path}")
            
            # Leer contenido para verificar estructura básica
            with open(command_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            required_patterns = [
                'class Command',
                'add_arguments',
                'handle',
                'RAGService',
                'IntelligenceCollection'
            ]
            
            for pattern in required_patterns:
                if pattern in content:
                    print(f"✓ Patrón '{pattern}' encontrado")
                else:
                    print(f"✗ Patrón '{pattern}' no encontrado")
                    return False
                    
            return True
        else:
            print(f"✗ Archivo del comando no encontrado: {command_path}")
            return False
            
    except Exception as e:
        print(f"✗ Error en prueba de comando: {e}")
        return False


def test_criterion_4_celery_beat():
    """Prueba 4: Pipeline automático con Celery Beat."""
    print("\n=== PRUEBA 4: Celery Beat ===")
    
    try:
        # Verificar configuración en celery.py
        celery_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'colas', 'celery.py'
        )
        
        if os.path.exists(celery_path):
            print(f"✓ Archivo celery.py encontrado")
            
            with open(celery_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Verificar tareas RAG en beat_schedule
            rag_tasks = [
                'sincronizar-colecciones-rag-cada-6-horas',
                'generar-embeddings-pendientes-cada-hora',
                'verificar-estado-rag-cada-12-horas',
                'limpiar-documentos-antiguos-cada-dia'
            ]
            
            for task in rag_tasks:
                if task in content:
                    print(f"✓ Tarea '{task}' configurada")
                else:
                    print(f"✗ Tarea '{task}' no configurada")
                    return False
                    
            return True
        else:
            print(f"✗ Archivo celery.py no encontrado")
            return False
            
    except Exception as e:
        print(f"✗ Error en prueba de Celery Beat: {e}")
        return False


def test_criterion_5_llm_integration():
    """Prueba 5: Integración con LLM."""
    print("\n=== PRUEBA 5: Integración LLM ===")
    
    try:
        # Verificar que la clase existe y tiene métodos requeridos
        required_methods = [
            'generate_rag_response',
            'analyze_query_intent',
            'extract_structured_data',
            'test_connection'
        ]
        
        for method in required_methods:
            if hasattr(LLMService, method):
                print(f"✓ Método '{method}' presente")
            else:
                print(f"✗ Método '{method}' faltante")
                return False
        
        # Verificar configuración
        print(f"✓ URL API: {LLMService.DEEPSEEK_API_URL}")
        print(f"✓ Modelo: {LLMService.DEEPSEEK_MODEL}")
        
        # Verificar variables de entorno
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if api_key:
            print(f"✓ API Key configurada (longitud: {len(api_key)})")
        else:
            print("⚠ API Key no configurada (esto es normal en pruebas)")
            
        return True
        
    except Exception as e:
        print(f"✗ Error en prueba de integración LLM: {e}")
        return False


def test_criterion_6_environment_variables():
    """Prueba 6: Variables de entorno configuradas."""
    print("\n=== PRUEBA 6: Variables de entorno ===")
    
    try:
        # Variables requeridas según SPEC-003
        required_vars = [
            'DEEPSEEK_API_KEY',
            'RAG_SIMILARITY_THRESHOLD',
            'RAG_MAX_RESULTS',
            'RAG_BATCH_SIZE',
            'MAX_RAG_CONTEXT_DOCUMENTS',
            'MIN_SIMILARITY_THRESHOLD',
            'DEEPSEEK_MAX_TOKENS',
            'DEEPSEEK_TEMPERATURE'
        ]
        
        all_present = True
        for var in required_vars:
            value = os.environ.get(var)
            if value:
                print(f"✓ {var} = {value[:20]}{'...' if len(str(value)) > 20 else ''}")
            else:
                print(f"✗ {var} no configurada")
                all_present = False
                
        return all_present
        
    except Exception as e:
        print(f"✗ Error en prueba de variables de entorno: {e}")
        return False


def test_criterion_7_test_endpoints():
    """Prueba 7: Endpoints de prueba implementados."""
    print("\n=== PRUEBA 7: Endpoints de prueba ===")
    
    try:
        # Verificar views.py
        views_path = os.path.join(
            os.path.dirname(__file__),
            'intelligence', 'views.py'
        )
        
        if os.path.exists(views_path):
            with open(views_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Verificar funciones de endpoint
            endpoint_functions = [
                'rag_test_endpoint',
                'rag_system_status'
            ]
            
            for func in endpoint_functions:
                if f'def {func}' in content:
                    print(f"✓ Función '{func}' presente")
                else:
                    print(f"✗ Función '{func}' faltante")
                    return False
            
            # Verificar URLs
            urls_path = os.path.join(
                os.path.dirname(__file__),
                'intelligence', 'urls.py'
            )
            
            if os.path.exists(urls_path):
                with open(urls_path, 'r', encoding='utf-8') as f:
                    urls_content = f.read()
                    
                url_patterns = [
                    "path('rag/test/'",
                    "path('rag/status/'"
                ]
                
                for pattern in url_patterns:
                    if pattern in urls_content:
                        print(f"✓ URL '{pattern}' configurada")
                    else:
                        print(f"✗ URL '{pattern}' no configurada")
                        return False
                        
                return True
            else:
                print(f"✗ Archivo urls.py no encontrado")
                return False
        else:
            print(f"✗ Archivo views.py no encontrado")
            return False
            
    except Exception as e:
        print(f"✗ Error en prueba de endpoints: {e}")
        return False


def main():
    """Ejecutar todas las pruebas de criterios de éxito."""
    print("=" * 60)
    print("PRUEBA DE CRITERIOS DE ÉXITO - SPEC-003 (SISTEMA RAG)")
    print("=" * 60)
    
    tests = [
        ("Modelos de base de datos", test_criterion_1_models),
        ("Servicio RAG", test_criterion_2_rag_service),
        ("Comando de sincronización", test_criterion_3_sync_command),
        ("Celery Beat", test_criterion_4_celery_beat),
        ("Integración LLM", test_criterion_5_llm_integration),
        ("Variables de entorno", test_criterion_6_environment_variables),
        ("Endpoints de prueba", test_criterion_7_test_endpoints),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ Error ejecutando prueba '{test_name}': {e}")
            results.append((test_name, False))
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE CRITERIOS DE ÉXITO")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASÓ" if success else "✗ FALLÓ"
        print(f"{status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} criterios cumplidos ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n✅ ¡TODOS LOS CRITERIOS DE SPEC-003 CUMPLIDOS!")
        print("El sistema RAG está implementado correctamente.")
    else:
        print(f"\n⚠ {total - passed} criterio(s) pendiente(s)")
        print("Revisar las implementaciones faltantes.")
    
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)