import requests
import time
import sys

print("Probando conexión al servidor Django...")
time.sleep(2)  # Dar tiempo al servidor para iniciar

try:
    response = requests.get('http://localhost:8000/eventos/', timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.text)} caracteres")
    
    if response.status_code == 200:
        print("¡Éxito! La página de eventos se carga correctamente.")
        
        # Verificar elementos clave
        if 'Eventos' in response.text:
            print("- Título 'Eventos' encontrado")
        if 'Filtrar' in response.text:
            print("- Formulario de filtros encontrado")
        if 'table' in response.text:
            print("- Tabla de eventos presente")
        
        # Buscar indicadores de eventos
        if 'eventos encontrados' in response.text.lower():
            print("- Contador de eventos presente")
        
        # Verificar que no haya errores de base de datos
        if 'ProgrammingError' in response.text or 'Invalid object name' in response.text:
            print("ERROR: Se detectó un error de base de datos en la respuesta")
            sys.exit(1)
        else:
            print("- No se detectaron errores de base de datos")
            
    else:
        print(f"Error: El servidor devolvió código {response.status_code}")
        print(f"Primeros 500 caracteres de la respuesta:\n{response.text[:500]}")
        sys.exit(1)
        
except requests.exceptions.ConnectionError:
    print("Error: No se puede conectar al servidor. Asegúrate de que esté ejecutándose.")
    sys.exit(1)
except Exception as e:
    print(f"Error inesperado: {e}")
    sys.exit(1)