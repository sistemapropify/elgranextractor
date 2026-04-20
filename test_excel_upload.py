import requests
import os

# URL del endpoint de subida
url = "http://127.0.0.1:8000/api/v1/intelligence/chat-web/upload/"

# Archivo Excel de prueba
file_path = "test_excel.xlsx"

if not os.path.exists(file_path):
    print(f"Error: El archivo {file_path} no existe")
    exit(1)

# Leer el archivo
with open(file_path, 'rb') as f:
    files = {'file': (os.path.basename(file_path), f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    
    # Datos adicionales (opcional)
    data = {
        'user_id': 'test_user_123',
        'conversation_id': 'test_conversation_456'
    }
    
    # Headers - necesitamos un token CSRF real para pruebas
    # Primero obtengamos uno de la sesión
    session = requests.Session()
    
    # Obtener la página principal para obtener token CSRF
    try:
        home_response = session.get("http://127.0.0.1:8000/api/v1/intelligence/chat-web/")
        print(f"Home status: {home_response.status_code}")
    except:
        print("No se pudo obtener token CSRF, usando placeholder")
    
    headers = {
        'X-CSRFToken': 'test_token_placeholder'  # En pruebas reales necesitaríamos extraer el token real
    }
    
    print(f"Enviando archivo: {file_path}")
    print(f"Tamaño: {os.path.getsize(file_path)} bytes")
    print(f"Tipo MIME: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    try:
        response = session.post(url, files=files, data=data, headers=headers)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✓ Subida exitosa")
            # Verificar la respuesta JSON
            try:
                json_response = response.json()
                if json_response.get('success'):
                    print(f"✓ Archivo procesado: {json_response.get('file_info', {}).get('filename', 'N/A')}")
                else:
                    print(f"✗ Error en backend: {json_response.get('error', 'Error desconocido')}")
            except:
                print("✓ Respuesta recibida (no JSON)")
        elif response.status_code == 400:
            print("✗ Error 400 - Bad Request")
            print("Posibles causas:")
            print("1. Validación de tipo MIME falló en frontend o backend")
            print("2. Token CSRF inválido")
            print("3. Error en el backend de validación")
            print("4. El archivo excede el tamaño máximo")
        elif response.status_code == 403:
            print("✗ Error 403 - Forbidden (CSRF token missing or incorrect)")
        elif response.status_code == 404:
            print("✗ Error 404 - Endpoint no encontrado")
        else:
            print(f"✗ Error {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error de conexión: {e}")

# También probar con un archivo .xls (formato antiguo)
print("\n" + "="*60)
print("Información sobre tipos MIME de Excel")
print("="*60)
print("Tipos MIME comunes para archivos Excel:")
print("1. .xlsx: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
print("2. .xls: application/vnd.ms-excel")
print("3. Otros posibles: application/excel, application/x-excel, application/x-msexcel")
print("\nEl navegador puede reportar diferentes tipos MIME dependiendo del sistema operativo.")
print("\nTipos MIME agregados en la validación mejorada:")
print("- application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
print("- application/vnd.ms-excel")
print("- application/excel")
print("- application/x-excel")
print("- application/x-msexcel")
print("- También validación por extensión: .xlsx, .xls")