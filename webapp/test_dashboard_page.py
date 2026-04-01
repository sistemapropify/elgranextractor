#!/usr/bin/env python
"""
Script para probar la carga del dashboard de visitas.
"""
import requests
import sys

def test_dashboard():
    url = "http://localhost:8000/propifai/dashboard/visitas/"
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        
        # Verificar si la página contiene elementos clave
        html = response.text
        if '<title>' in html:
            # Extraer título
            import re
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if title_match:
                print(f"Título: {title_match.group(1)}")
        
        # Verificar si contiene el tbody
        if 'id="properties-tbody"' in html:
            print("OK: Elemento properties-tbody encontrado en HTML")
        else:
            print("ERROR: Elemento properties-tbody NO encontrado en HTML")
            # Buscar tbody alternativo
            if 'id="properties-table-body"' in html:
                print("  (pero encontré properties-table-body)")
        
        # Verificar si contiene el script de inicialización
        if 'propertiesData = JSON.parse' in html or 'var propertiesData =' in html:
            print("OK: JavaScript propertiesData encontrado")
        else:
            print("ERROR: JavaScript propertiesData NO encontrado")
            
        # Verificar si hay datos JSON en la página
        import json
        # Buscar patrones de JSON
        import re
        json_pattern = r'propertiesData\s*=\s*JSON\.parse\(\s*["\'](.*?)["\']\s*\)'
        match = re.search(json_pattern, html, re.DOTALL)
        if match:
            print("OK: JSON encontrado en propertiesData")
            # Intentar decodificar
            try:
                json_str = match.group(1).replace('\\"', '"').replace("\\'", "'")
                # Esto es complejo, mejor solo confirmar que existe
                print(f"  Longitud del JSON: {len(json_str)} caracteres")
            except:
                pass
        else:
            # Buscar otra forma
            if 'properties_json' in html:
                print("OK: Variable properties_json encontrada en template")
            else:
                print("ERROR: No se encontró JSON de propiedades")
        
        # Verificar errores JavaScript
        if 'console.error' in html:
            print("ADVERTENCIA: Se encontraron console.error en el código")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: No se pudo conectar al servidor. ¿Está corriendo Django?")
        print("  Ejecuta: cd webapp && py manage.py runserver")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_dashboard()