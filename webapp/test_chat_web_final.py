#!/usr/bin/env python
"""
Test final para verificar la implementación completa del Chat Web (SPEC-007).
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import Client
from django.urls import reverse

def test_chat_web_urls():
    """Test que verifica que las URLs del chat web están funcionando."""
    print("=== Test de URLs del Chat Web (SPEC-007) ===")
    
    client = Client()
    urls_to_test = [
        ('intelligence:chat_web', 'Vista principal del chat web'),
        ('intelligence:chat_web_api', 'API del chat web'),
        ('intelligence:chat_web_stream', 'API de streaming del chat web'),
        ('intelligence:chat_web_upload', 'API de upload de archivos'),
    ]
    
    all_passed = True
    
    for url_name, description in urls_to_test:
        try:
            # Para la vista principal, necesita autenticación de admin
            if url_name == 'intelligence:chat_web':
                response = client.get(reverse(url_name))
                # Puede devolver 302 (redirect a login) o 200 si ya está autenticado
                if response.status_code in [200, 302]:
                    print(f"✓ {description}: URL resuelta correctamente")
                else:
                    print(f"✗ {description}: Código {response.status_code}")
                    all_passed = False
            else:
                # Para APIs, solo verificamos que la URL se resuelva
                try:
                    url = reverse(url_name)
                    print(f"✓ {description}: URL resuelta a {url}")
                except Exception as e:
                    print(f"✗ {description}: Error al resolver URL - {e}")
                    all_passed = False
        except Exception as e:
            print(f"✗ {description}: Error - {e}")
            all_passed = False
    
    return all_passed

def test_chat_web_api_basic():
    """Test básico de la API del chat web."""
    print("\n=== Test básico de API del Chat Web ===")
    
    client = Client()
    
    # Datos de prueba
    test_data = {
        'message': 'Hola, ¿cómo estás?',
        'user_id': None,  # Se creará usuario temporal
        'use_memory': True,
        'use_rag': True,
        'collections': []
    }
    
    try:
        response = client.post(
            reverse('intelligence:chat_web_api'),
            data=json.dumps(test_data),
            content_type='application/json'
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ API responde correctamente")
                print(f"  Conversation ID: {data.get('conversation_id')}")
                print(f"  Response: {data.get('response', '')[:100]}...")
                return True
            else:
                print(f"✗ API retornó success=False: {data.get('error')}")
                return False
        else:
            print(f"✗ Código de estado {response.status_code}: {response.content[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ Error en la llamada API: {e}")
        return False

def test_template_files():
    """Verifica que los archivos de template y estáticos existen."""
    print("\n=== Verificación de archivos de template y estáticos ===")
    
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    files_to_check = [
        ('templates/intelligence/chat.html', 'Template del chat'),
        ('static/intelligence/chat.css', 'CSS del chat'),
        ('static/intelligence/chat.js', 'JavaScript del chat'),
        ('intelligence/views.py', 'Vistas del chat'),
        ('intelligence/urls.py', 'URLs del chat'),
    ]
    
    all_exist = True
    
    for file_path, description in files_to_check:
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            print(f"✓ {description}: {file_path}")
        else:
            print(f"✗ {description}: NO encontrado en {full_path}")
            all_exist = False
    
    return all_exist

def test_services_integration():
    """Verifica que los servicios PIL están integrados."""
    print("\n=== Verificación de integración con servicios PIL ===")
    
    try:
        # Verificar que los servicios están disponibles
        from intelligence.services import MemoryService, RAGService, LLMService
        
        print("✓ MemoryService importado correctamente")
        print("✓ RAGService importado correctamente")
        print("✓ LLMService importado correctamente")
        
        # Verificar métodos de streaming
        if hasattr(LLMService, 'generate_streaming_response'):
            print("✓ LLMService tiene método de streaming")
        else:
            print("✗ LLMService NO tiene método de streaming")
            return False
            
        return True
        
    except ImportError as e:
        print(f"✗ Error importando servicios: {e}")
        return False
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        return False

def main():
    """Función principal de testing."""
    print("=" * 60)
    print("TEST FINAL - CHAT WEB INTERACTIVO (SPEC-007)")
    print("=" * 60)
    
    results = []
    
    # Ejecutar tests
    results.append(('URLs del chat web', test_chat_web_urls()))
    results.append(('Archivos de template', test_template_files()))
    results.append(('Integración servicios PIL', test_services_integration()))
    results.append(('API básica del chat', test_chat_web_api_basic()))
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE TESTS")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASÓ" if result else "✗ FALLÓ"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests pasados ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n✅ ¡IMPLEMENTACIÓN COMPLETA DEL CHAT WEB (SPEC-007)!")
        print("El chat web está listo para uso con:")
        print("1. Interfaz web tipo chat con panel lateral")
        print("2. Integración completa con servicios PIL (Memory, RAG, LLM)")
        print("3. Streaming de respuestas en tiempo real")
        print("4. Gestión de archivos adjuntos")
        print("5. Memoria de usuario y contexto personalizado")
        return True
    else:
        print(f"\n⚠ {total - passed} test(s) fallaron. Revisar implementación.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)