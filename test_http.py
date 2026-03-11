#!/usr/bin/env python
"""
Test HTTP real para verificar la vista en el servidor.
"""
import requests
import sys

print("=== TEST HTTP REAL ===")
print()

# URL base del servidor
base_url = "http://localhost:8000"

# Test 1: Filtrar solo Propify
print("1. Test: Filtrar solo Propify")
url = f"{base_url}/ingestas/propiedades/?fuente_propify=propify"
print(f"   URL: {url}")

try:
    response = requests.get(url, timeout=10)
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        # Buscar en el HTML el contador de Propify
        html = response.text
        
        # Buscar el contador en el HTML
        import re
        
        # Buscar el patrón del contador
        pattern = r'propiedades\s*\(.*?\+.*?\+.*?(\d+)\s*propify\)'
        match = re.search(pattern, html)
        if match:
            conteo_propify = match.group(1)
            print(f"   Contador Propify encontrado en HTML: {conteo_propify}")
        else:
            print(f"   Contador Propify NO encontrado en HTML")
            # Buscar cualquier mención a "propify" en el HTML
            if 'propify' in html.lower():
                print(f"   'propify' mencionado en HTML: SI")
                # Extraer un fragmento del HTML donde aparece
                idx = html.lower().find('propify')
                fragmento = html[max(0, idx-100):min(len(html), idx+100)]
                print(f"   Fragmento: ...{fragmento}...")
            else:
                print(f"   'propify' mencionado en HTML: NO")
        
        # Buscar propiedades en el HTML
        if 'property-card' in html:
            print(f"   Tarjetas de propiedad encontradas: SI")
            # Contar cuántas tarjetas hay
            count = html.count('property-card')
            print(f"   Número de tarjetas property-card: {count}")
        else:
            print(f"   Tarjetas de propiedad encontradas: NO")
            
    else:
        print(f"   ERROR: Status code no es 200")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 2: Mostrar todas las fuentes (por defecto)
print("2. Test: Mostrar todas las fuentes (por defecto)")
url2 = f"{base_url}/ingestas/propiedades/"
print(f"   URL: {url2}")

try:
    response2 = requests.get(url2, timeout=10)
    print(f"   Status Code: {response2.status_code}")
    
    if response2.status_code == 200:
        html2 = response2.text
        
        # Buscar el contador
        pattern = r'propiedades\s*\(.*?\+.*?\+.*?(\d+)\s*propify\)'
        match = re.search(pattern, html2)
        if match:
            conteo_propify = match.group(1)
            print(f"   Contador Propify encontrado: {conteo_propify}")
        else:
            print(f"   Contador Propify NO encontrado")
            
except Exception as e:
    print(f"   ERROR: {e}")

print()
print("=== FIN TEST HTTP ===")