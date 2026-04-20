import requests
import json
import sys
import uuid

# URL del endpoint
url = 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/api/'

# Datos de prueba - usar email en lugar de user_id para evitar problemas de UUID
data = {
    'message': 'Hola, ¿cómo estás?',
    'email': 'test_user@propifai.com',
    'use_memory': True,
    'use_rag': True,
    'collections': []
}

print("Probando endpoint del chat...")
print(f"URL: {url}")
print(f"Datos: {json.dumps(data, indent=2)}")

try:
    response = requests.post(url, json=data, timeout=10)
    print(f'\nStatus Code: {response.status_code}')
    
    if response.status_code == 200:
        print("¡Éxito! El endpoint responde correctamente.")
        try:
            response_json = response.json()
            print(f"Respuesta JSON: {json.dumps(response_json, indent=2)[:1000]}...")
        except:
            print(f"Respuesta (texto): {response.text[:500]}")
    elif response.status_code == 400:
        print("Error 400 - Bad Request")
        print(f"Respuesta: {response.text[:500]}")
        print("\nProbando con UUID válido...")
        
        # Intentar con un UUID válido
        data_with_uuid = {
            'message': 'Hola, ¿cómo estás?',
            'user_id': str(uuid.uuid4()),
            'use_memory': True,
            'use_rag': True,
            'collections': []
        }
        
        response2 = requests.post(url, json=data_with_uuid, timeout=10)
        print(f'\nStatus Code con UUID: {response2.status_code}')
        print(f"Respuesta: {response2.text[:500]}")
    else:
        print(f"Error HTTP: {response.status_code}")
        print(f"Respuesta: {response.text[:500]}")
        
except requests.exceptions.ConnectionError:
    print("Error: No se puede conectar al servidor. ¿Está corriendo el servidor Django?")
    sys.exit(1)
except requests.exceptions.Timeout:
    print("Error: Timeout al conectar con el servidor.")
    sys.exit(1)
except Exception as e:
    print(f'Error inesperado: {e}')
    sys.exit(1)