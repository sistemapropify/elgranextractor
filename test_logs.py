#!/usr/bin/env python3
"""
Test para ver logs de depuración
"""
import urllib.request
import urllib.parse
import time

def test_con_logs():
    print("=== TEST CON LOGS ===")
    
    url = "http://localhost:8000/ingestas/propiedades/"
    params = {'fuente_propify': 'propify'}
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    print(f"URL: {full_url}")
    print("Haciendo petición... (espera 5 segundos para ver logs)")
    
    try:
        # Hacer la petición
        req = urllib.request.Request(full_url)
        response = urllib.request.urlopen(req, timeout=10)
        html = response.read().decode('utf-8')
        
        print(f"Status: {response.status}")
        
        # Buscar el contador
        if 'propiedades (' in html:
            start = html.find('propiedades (')
            end = html.find(')', start)
            if start != -1 and end != -1:
                counter_text = html[start:end+1]
                print(f"Contador en HTML: {counter_text}")
        
        # Verificar Propify
        propify_count = html.count('data-es-propify="true"')
        print(f"Propiedades con data-es-propify=\"true\": {propify_count}")
        
        if propify_count == 0:
            print("\n¡PROBLEMA: No hay propiedades Propify en el HTML!")
            print("Revisa los logs del servidor para ver los mensajes DEBUG.")
        else:
            print(f"\n¡ÉXITO: Se encontraron {propify_count} propiedades Propify!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_con_logs()