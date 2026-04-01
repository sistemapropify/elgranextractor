#!/usr/bin/env python
import requests
import re

url = "http://localhost:8000/propifai/dashboard/visitas/"

print("Obteniendo página...")
response = requests.get(url, timeout=10)
html = response.text

# Buscar el bloque try-catch y extraer el error
pattern = r'try\s*{([^}]+(?:\{[^}]*\}[^}]*)*)}[^{]*catch\s*\(error\)\s*{([^}]+)}'
match = re.search(pattern, html, re.DOTALL)

if match:
    try_block = match.group(1)
    catch_block = match.group(2)
    
    print("=== BLOQUE CATCH ENCONTRADO ===")
    print(catch_block[:500])
    
    # Buscar líneas específicas con console.error
    lines = html.split('\n')
    for i, line in enumerate(lines):
        if 'console.error' in line and 'Error en inicialización' in line:
            print(f"\n=== ERROR EN LÍNEA {i+1} ===")
            print(f"Línea: {line.strip()}")
            # Mostrar contexto
            for j in range(max(0, i-3), min(len(lines), i+4)):
                prefix = ">>> " if j == i else "    "
                print(f"{prefix}{j+1}: {lines[j].strip()}")
else:
    print("No se encontró bloque try-catch")
    
# También buscar cualquier mensaje de error que pueda estar en la página
if 'errorDiv' in html:
    print("\n=== POSIBLE DIV DE ERROR EN PÁGINA ===")
    # Buscar la creación del errorDiv
    error_pattern = r'errorDiv\.innerHTML\s*=\s*["\']([^"\']+)["\']'
    error_match = re.search(error_pattern, html, re.DOTALL)
    if error_match:
        print("Contenido del errorDiv:")
        print(error_match.group(1)[:500])