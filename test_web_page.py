#!/usr/bin/env python
"""
Script para probar la página web del matching masivo.
"""
import os
import sys
import django
import requests
import time

# Configurar Django para usar modelos si es necesario
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def test_masivo_page():
    """Test de la página /matching/masivo/"""
    print("=== TEST PÁGINA WEB MATCHING MASIVO ===")
    
    # Esperar un momento para que el servidor inicie
    time.sleep(2)
    
    url = "http://127.0.0.1:8000/matching/masivo/"
    
    try:
        print(f"Realizando solicitud GET a {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Tamaño de respuesta: {len(response.text)} bytes")
        
        if response.status_code == 200:
            print("✓ La página se cargó exitosamente")
            
            # Verificar contenido clave
            content = response.text
            
            # Verificar que no haya errores de template
            if "NoReverseMatch" in content:
                print("✗ ERROR: Se encontró NoReverseMatch en la página")
                return False
            if "Page not found" in content or "404" in content:
                print("✗ ERROR: Se encontró error 404 en la página")
                return False
            if "Server Error" in content or "500" in content:
                print("✗ ERROR: Se encontró error 500 en la página")
                return False
            
            # Verificar elementos esperados
            checks = [
                ("Matching Masivo", "Título de la página"),
                ("tablaRequerimientos", "Tabla de requerimientos"),
                ("Propiedad Match", "Columna de propiedad match"),
                ("PROP0000", "Código de propiedad (aproximado)"),
                ("0.556%", "Porcentaje de match"),
            ]
            
            for text, description in checks:
                if text in content:
                    print(f"✓ Se encontró '{text}' ({description})")
                else:
                    print(f"⚠ No se encontró '{text}' ({description})")
            
            # Verificar enlaces de admin (no deberían causar 404)
            if "/admin/propifai/propifaiproperty/" in content:
                print("⚠ Se encontró enlace al admin - verificar que no cause 404")
            
            return True
        else:
            print(f"✗ ERROR: La página devolvió código {response.status_code}")
            print(f"Primeros 500 caracteres de respuesta:")
            print(response.text[:500])
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: No se pudo conectar al servidor. ¿Está corriendo?")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False
    
    print("\n=== TEST COMPLETADO ===")

if __name__ == '__main__':
    success = test_masivo_page()
    sys.exit(0 if success else 1)