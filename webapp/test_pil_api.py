"""
Script de prueba para verificar la funcionalidad básica del PIL.
"""
import requests
import json
import sys
import uuid

BASE_URL = 'http://localhost:8000/api/v1/intelligence'

def test_health_check():
    """Probar endpoint de salud."""
    print("1. Probando health check...")
    try:
        response = requests.get(f'{BASE_URL}/health/')
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] Health check OK: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            return True
        else:
            print(f"   [ERROR] Health check falló: {response.status_code}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error de conexión: {e}")
        return False

def test_chat_endpoint():
    """Probar endpoint de chat."""
    print("\n2. Probando endpoint de chat...")
    
    # Datos de prueba
    payload = {
        'message': 'Hola, estoy buscando un departamento en Cayma',
        'phone': '999888777',
        'metadata': {'name': 'Carlos', 'preferencia': 'departamento'}
    }
    
    headers = {
        'X-App-ID': 'web-clientes',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(
            f'{BASE_URL}/chat/',
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] Chat endpoint OK: {response.status_code}")
            print(f"   Response: {data.get('response')[:80]}...")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   User ID: {data.get('user_id')}")
            return True
        else:
            print(f"   [ERROR] Chat endpoint falló: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error de conexión: {e}")
        return False

def test_chat_with_existing_session():
    """Probar chat con sesión existente."""
    print("\n3. Probando chat con sesión existente...")
    
    # Primera solicitud
    session_id = f'test_session_{uuid.uuid4().hex[:8]}'
    payload1 = {
        'message': 'Mi presupuesto es 80,000 dólares',
        'phone': '999888777',
        'session_id': session_id
    }
    
    headers = {'X-App-ID': 'web-clientes'}
    
    try:
        response1 = requests.post(f'{BASE_URL}/chat/', json=payload1, headers=headers)
        if response1.status_code != 200:
            print(f"   [ERROR] Primera solicitud falló: {response1.status_code}")
            return False
        
        data1 = response1.json()
        user_id = data1.get('user_id')
        
        # Segunda solicitud con misma sesión
        payload2 = {
            'message': '¿Qué opciones tienes?',
            'user_id': user_id,
            'session_id': session_id
        }
        
        response2 = requests.post(f'{BASE_URL}/chat/', json=payload2, headers=headers)
        if response2.status_code == 200:
            data2 = response2.json()
            print(f"   [OK] Chat con sesión existente OK")
            print(f"   Response: {data2.get('response')[:80]}...")
            return True
        else:
            print(f"   [ERROR] Segunda solicitud falló: {response2.status_code}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False

def test_different_app_levels():
    """Probar diferentes niveles de app."""
    print("\n4. Probando diferentes niveles de app...")
    
    apps_to_test = [
        ('web-clientes', 2),
        ('dashboard-admin', 3),
        ('whatsapp-bot', 1)
    ]
    
    for app_id, expected_level in apps_to_test:
        payload = {
            'message': f'Prueba de nivel {expected_level}',
            'phone': f'999{expected_level}111'
        }
        
        headers = {'X-App-ID': app_id}
        
        try:
            response = requests.post(f'{BASE_URL}/chat/', json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ App {app_id} (nivel {expected_level}) responde OK")
                # Verificar que la respuesta menciona el nivel correcto
                response_text = data.get('response', '')
                if f'Nivel {expected_level}' in response_text:
                    print(f"     Respuesta correctamente personalizada por nivel")
            else:
                print(f"   ✗ App {app_id} falló: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Error con app {app_id}: {e}")

def main():
    print("=== PRUEBAS DEL PROPIFAI INTELLIGENCE LAYER (PIL) ===")
    print(f"Base URL: {BASE_URL}")
    print()
    
    # Verificar si el servidor está corriendo
    try:
        requests.get('http://localhost:8000/', timeout=2)
    except:
        print("⚠️  ADVERTENCIA: El servidor Django no parece estar corriendo en localhost:8000")
        print("   Ejecuta: python manage.py runserver")
        print("   Continuando con pruebas de API...")
    
    tests_passed = 0
    tests_total = 0
    
    # Ejecutar pruebas
    if test_health_check():
        tests_passed += 1
    tests_total += 1
    
    if test_chat_endpoint():
        tests_passed += 1
    tests_total += 1
    
    if test_chat_with_existing_session():
        tests_passed += 1
    tests_total += 1
    
    test_different_app_levels()
    
    print("\n=== RESUMEN DE PRUEBAS ===")
    print(f"Pruebas pasadas: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("✅ Todas las pruebas básicas pasaron correctamente.")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")
    
    # Verificar criterios de éxito de la SPEC
    print("\n=== CRITERIOS DE ÉXITO SPEC-001 ===")
    print("[ ] Endpoint responde 200 con configuración correcta de la app")
    print("[ ] Usuario se crea automáticamente al primer mensaje")
    print("[ ] Conversación se guarda con mensajes en JSON")
    print("[ ] Configuraciones por defecto existen en base de datos")
    print("[ ] Django Admin permite ver y editar modelos")
    print("[ ] Migraciones aplican sin error en Azure SQL")
    print("\nNota: Los criterios marcados con [ ] deben verificarse manualmente.")

if __name__ == '__main__':
    main()