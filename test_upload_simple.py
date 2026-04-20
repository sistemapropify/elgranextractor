import requests
import os
import pandas as pd

# Crear archivo Excel de prueba
df = pd.DataFrame({'columna1': [1, 2, 3], 'columna2': ['a', 'b', 'c']})
test_file = 'test_upload_excel.xlsx'
df.to_excel(test_file, index=False)

print(f"Archivo de prueba creado: {test_file}")
print(f"Tamaño: {os.path.getsize(test_file)} bytes")

# URL del endpoint
url = "http://127.0.0.1:8000/api/v1/intelligence/chat-web/upload/"

# Preparar la solicitud
with open(test_file, 'rb') as f:
    files = {'file': (test_file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    
    # Para pruebas, podemos omitir el token CSRF o usar uno válido
    # En un entorno real necesitaríamos obtenerlo de la sesión
    headers = {
        'X-CSRFToken': 'test_token_for_dev'
    }
    
    data = {
        'user_id': 'test_user_123',
        'conversation_id': 'test_conv_456'
    }
    
    print(f"\nEnviando solicitud a: {url}")
    print(f"Tipo MIME: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    try:
        response = requests.post(url, files=files, data=data, headers=headers)
        
        print(f"\nRespuesta:")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ ¡Éxito! Archivo aceptado por el backend")
            try:
                json_resp = response.json()
                print(f"Respuesta JSON: {json_resp}")
                if json_resp.get('success'):
                    print("✓ Backend reporta éxito")
                else:
                    print(f"✗ Backend reporta error: {json_resp.get('error')}")
            except:
                print(f"Contenido: {response.text[:200]}...")
        elif response.status_code == 400:
            print("✗ Error 400 - Bad Request")
            print(f"Contenido: {response.text}")
            print("\nPosibles causas:")
            print("1. Validación de tipo MIME en backend aún falla")
            print("2. Token CSRF inválido")
            print("3. Tamaño de archivo excede límite")
        elif response.status_code == 403:
            print("✗ Error 403 - Forbidden (CSRF token)")
            print("Nota: En desarrollo, puedes deshabilitar temporalmente CSRF o usar un token válido")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"✗ Error de conexión: {e}")

# Limpiar
os.remove(test_file)
print(f"\nArchivo de prueba eliminado: {test_file}")

print("\n" + "="*60)
print("RESUMEN DE LA SOLUCIÓN IMPLEMENTADA")
print("="*60)
print("1. FRONTEND (chat.js):")
print("   - Tipos MIME agregados para Excel:")
print("     - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet (.xlsx)")
print("     - application/vnd.ms-excel (.xls)")
print("     - application/excel, application/x-excel, application/x-msexcel")
print("   - Validación por extensión como fallback")
print("   - Mensaje de error mejorado")
print()
print("2. BACKEND (views.py):")
print("   - Tipos MIME actualizados para coincidir con frontend")
print("   - Validación por extensión como fallback")
print("   - Mensajes de error más informativos")
print()
print("3. PRUEBAS:")
print("   - Script de prueba creado")
print("   - Archivo Excel de prueba generado automáticamente")
print("   - Validación de respuesta del backend")