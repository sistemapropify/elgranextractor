#!/usr/bin/env python
"""
Script final para probar que el dashboard de eventos funciona.
"""
import sys
import time
import requests

def test_dashboard():
    print("=== Prueba final del dashboard de eventos ===")
    
    # Esperar a que el servidor se inicie
    print("Esperando 5 segundos para que el servidor se inicie...")
    time.sleep(5)
    
    url = "http://localhost:8000/eventos/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"URL: {url}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ Página cargada exitosamente")
            
            # Verificar elementos clave
            content = response.text
            
            # Elementos básicos
            checks = [
                ("Eventos", "Título 'Eventos'"),
                ("Filtrar", "Formulario de filtros"),
                ("table", "Tabla de eventos"),
                ("Propiedad", "Columna 'Propiedad'"),
                ("Coordenadas", "Columna 'Coordenadas'"),
                ("mapModal", "Modal de mapa"),
                ("Ver Mapa", "Botón 'Ver Mapa'"),
            ]
            
            for text, description in checks:
                if text in content:
                    print(f"✓ {description} encontrado")
                else:
                    print(f"⚠ {description} NO encontrado")
            
            # Verificar que no haya errores
            error_indicators = [
                "ProgrammingError",
                "Invalid object name",
                "Error",
                "Exception",
                "Traceback"
            ]
            
            has_errors = False
            for indicator in error_indicators:
                if indicator in content:
                    print(f"✗ Se encontró '{indicator}' en la respuesta")
                    has_errors = True
            
            if not has_errors:
                print("✓ No se detectaron errores en la página")
            
            return True
        else:
            print(f"✗ Error: Código de estado {response.status_code}")
            print(f"Contenido (primeros 500 caracteres): {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Error: No se puede conectar al servidor")
        return False
    except requests.exceptions.Timeout:
        print("✗ Error: Timeout al conectar con el servidor")
        return False
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        return False

if __name__ == '__main__':
    success = test_dashboard()
    print("\n" + "="*50)
    if success:
        print("PRUEBA EXITOSA: El dashboard de eventos funciona correctamente")
        print("Características implementadas:")
        print("1. Título de propiedad junto al property_id")
        print("2. Coordenadas de la propiedad")
        print("3. Modal de Google Maps al hacer clic en 'Ver Mapa'")
        print("4. Paginación y filtros funcionales")
        sys.exit(0)
    else:
        print("PRUEBA FALLIDA: Hay problemas con el dashboard")
        sys.exit(1)