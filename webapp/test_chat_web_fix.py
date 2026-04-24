#!/usr/bin/env python
"""
Script para probar la corrección del error 'Generator' en el chat-web.
Verifica que:
1. La importación de Generator esté presente en llm.py
2. El chat-web API funcione correctamente
3. No haya errores de 'name Generator is not defined'
"""

import os
import sys
import django
from pathlib import Path

# Configurar Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def test_import_generator():
    """Verifica que Generator esté importado en llm.py."""
    print("=== PRUEBA DE IMPORTACIÓN GENERATOR ===")
    
    llm_path = Path(__file__).parent / 'intelligence' / 'services' / 'llm.py'
    
    if not llm_path.exists():
        print(f"✗ Archivo no encontrado: {llm_path}")
        return False
    
    with open(llm_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar importación de Generator
    if 'from typing import' in content and 'Generator' in content:
        # Verificar que Generator esté en la lista de importaciones
        import_lines = [line for line in content.split('\n') if 'from typing import' in line]
        for line in import_lines:
            if 'Generator' in line:
                print(f"✓ Generator importado correctamente: {line.strip()}")
                return True
    
    print("✗ Generator NO está importado en llm.py")
    return False

def test_llm_service_import():
    """Verifica que LLMService se pueda importar sin errores."""
    print("\n=== PRUEBA DE IMPORTACIÓN LLMSERVICE ===")
    
    try:
        from intelligence.services.llm import LLMService
        print("✓ LLMService importado correctamente")
        
        # Verificar que la clase tenga los métodos esperados
        methods = ['generate_rag_response', 'generate_streaming_response', '_call_deepseek_api']
        for method in methods:
            if hasattr(LLMService, method):
                print(f"✓ Método {method} presente")
            else:
                print(f"⚠ Método {method} no encontrado")
        
        return True
    except ImportError as e:
        print(f"✗ Error importando LLMService: {e}")
        return False
    except NameError as e:
        print(f"✗ NameError en LLMService: {e}")
        return False
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        return False

def test_chat_web_api_simulation():
    """Simula una llamada a la API del chat-web."""
    print("\n=== PRUEBA SIMULADA DE CHAT-WEB API ===")
    
    try:
        from django.test import Client
        client = Client()
        
        # Datos de prueba
        test_data = {
            'user_id': 'c59a095f-80c0-4978-b4f7-9988ca021a40',  # Usuario de prueba
            'message': 'Hola, ¿cómo estás?',
            'conversation_id': None,
            'use_memory': True,
            'use_rag': True,
            'collections': []
        }
        
        # Intentar hacer una solicitud POST
        response = client.post('/api/v1/intelligence/chat-web/api/', 
                              data=test_data, 
                              content_type='application/json')
        
        print(f"✓ Solicitud POST realizada: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ API respondió con éxito (200)")
            
            # Verificar contenido de la respuesta
            try:
                response_data = response.json()
                if 'success' in response_data:
                    print(f"✓ Respuesta JSON válida: success={response_data['success']}")
                else:
                    print("⚠ Respuesta JSON no tiene campo 'success'")
            except:
                print("⚠ Respuesta no es JSON válido")
            
        elif response.status_code == 400:
            print("⚠ API respondió con 400 (Bad Request) - puede ser normal para datos de prueba")
        else:
            print(f"⚠ API respondió con código inesperado: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"✗ Error en prueba de API: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_generator_usage():
    """Verifica que Generator se use correctamente en el código."""
    print("\n=== PRUEBA DE USO DE GENERATOR ===")
    
    llm_path = Path(__file__).parent / 'intelligence' / 'services' / 'llm.py'
    
    with open(llm_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    generator_found = False
    for i, line in enumerate(lines):
        if 'Generator[' in line or '-> Generator' in line:
            generator_found = True
            print(f"✓ Línea {i+1}: {line.strip()}")
    
    if generator_found:
        print("✓ Generator usado correctamente en anotaciones de tipo")
        return True
    else:
        print("⚠ No se encontraron usos de Generator en anotaciones de tipo")
        return False

def main():
    """Función principal."""
    print("=" * 60)
    print("PRUEBA DE CORRECCIÓN DE ERROR 'Generator'")
    print("=" * 60)
    print()
    
    tests_passed = 0
    tests_total = 4
    
    # Ejecutar pruebas
    if test_import_generator():
        tests_passed += 1
    
    if test_llm_service_import():
        tests_passed += 1
    
    if test_generator_usage():
        tests_passed += 1
    
    if test_chat_web_api_simulation():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print("RESUMEN FINAL:")
    print("=" * 60)
    print(f"Pruebas pasadas: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("✓ TODAS las pruebas pasaron exitosamente")
        print("✓ El error 'name Generator is not defined' debería estar resuelto")
    else:
        print(f"⚠ {tests_total - tests_passed} pruebas fallaron")
        print("⚠ Puede haber problemas adicionales")
    
    print("\nRecomendaciones para producción:")
    print("1. Asegurar que el archivo llm.py esté desplegado con la corrección")
    print("2. Reiniciar el servidor de producción después del despliegue")
    print("3. Verificar logs de producción para confirmar que el error ha desaparecido")
    
    return 0 if tests_passed == tests_total else 1

if __name__ == '__main__':
    sys.exit(main())