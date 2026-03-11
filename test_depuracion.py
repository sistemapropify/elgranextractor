#!/usr/bin/env python3
"""
Test para ver los logs de depuración
"""
import urllib.request
import urllib.parse

def test_filtro_propify():
    print("=== TEST FILTRO PROPIY ===")
    
    url = "http://localhost:8000/ingestas/propiedades/"
    params = {'fuente_propify': 'propify'}
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    print(f"URL: {full_url}")
    
    try:
        # Hacer la petición
        req = urllib.request.Request(full_url)
        response = urllib.request.urlopen(req, timeout=30)
        html = response.read().decode('utf-8')
        
        print(f"Status: {response.status}")
        
        # Buscar el contador en el HTML
        if 'propiedades (' in html:
            # Extraer la línea con el contador
            start = html.find('propiedades (')
            end = html.find(')', start)
            if start != -1 and end != -1:
                counter_text = html[start:end+1]
                print(f"Contador encontrado: {counter_text}")
        
        # Buscar si hay propiedades Propify
        if 'data-es-propify="true"' in html:
            count = html.count('data-es-propify="true"')
            print(f"Se encontraron {count} propiedades con data-es-propify=\"true\"")
        else:
            print("NO se encontraron propiedades con data-es-propify=\"true\"")
            
        # Verificar badges Propify
        if '>Propify<' in html:
            count = html.count('>Propify<')
            print(f"Se encontraron {count} badges 'Propify'")
        else:
            print("NO se encontraron badges 'Propify'")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_filtro_propify()