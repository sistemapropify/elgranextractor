import requests
import sys

try:
    resp = requests.get('http://127.0.0.1:8000/analisis-crm/', timeout=10)
    if resp.status_code == 200:
        # Buscar la tabla de depuración
        import re
        # Extraer el div con bg-light
        pattern = r'<div class="mt-3 p-3 bg-light border rounded">(.*?)</div>'
        match = re.search(pattern, resp.text, re.DOTALL)
        if match:
            print("DEBUG TABLE FOUND:")
            print(match.group(0)[:2000])
        else:
            print("Debug table not found. Maybe template not rendered.")
            # Imprimir un fragmento del HTML para verificar
            print(resp.text[:2000])
    else:
        print(f"Error: {resp.status_code}")
except Exception as e:
    print(f"Request failed: {e}")