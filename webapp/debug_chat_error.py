import requests
import json
import sys

# Configurar para ver el traceback completo
import logging
logging.basicConfig(level=logging.DEBUG)

url = 'http://127.0.0.1:8000/api/v1/intelligence/chat-web/api/'
data = {
    'message': 'Hola, prueba del chat',
    'email': 'test@example.com',
    'use_memory': True,
    'use_rag': True,
    'collections': []
}

print('=== Probando endpoint de chat ===')
print(f'URL: {url}')
print(f'Datos: {json.dumps(data, indent=2)}')

try:
    # Hacer la solicitud con más información de depuración
    import http.client as http_client
    http_client.HTTPConnection.debuglevel = 1
    
    response = requests.post(url, json=data, timeout=10)
    print(f'\nStatus Code: {response.status_code}')
    print(f'Headers: {dict(response.headers)}')
    
    if response.status_code == 500:
        print('\n=== ERROR 500 - Traceback del servidor ===')
        # Intentar obtener más información del cuerpo de respuesta
        print(f'Response Body: {response.text}')
        
        # Verificar si hay un traceback en el HTML (si Django está en debug)
        if '<pre' in response.text:
            print('\nParece que hay un traceback HTML en la respuesta')
    else:
        print(f'Response: {response.text}')
        
except requests.exceptions.ConnectionError as e:
    print(f'Error de conexión: {e}')
except Exception as e:
    print(f'Error inesperado: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()

# También probar con user_id en lugar de email
print('\n\n=== Probando con user_id ===')
data2 = {
    'message': 'Hola, prueba con user_id',
    'user_id': '00000000-0000-0000-0000-000000000000',  # UUID inválido
    'use_memory': False,
    'use_rag': False,
}
try:
    response2 = requests.post(url, json=data2, timeout=10)
    print(f'Status: {response2.status_code}')
    print(f'Response: {response2.text}')
except Exception as e:
    print(f'Error: {e}')