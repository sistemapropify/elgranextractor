#!/usr/bin/env python
import requests
import re

url = "http://localhost:8000/propifai/dashboard/visitas/"

print("Obteniendo página completa...")
response = requests.get(url, timeout=10)
html = response.text

# Buscar todas las líneas con console.error
lines = html.split('\n')
error_lines = []
for i, line in enumerate(lines):
    if 'console.error' in line:
        error_lines.append((i+1, line.strip()))
        
print(f"Encontradas {len(error_lines)} líneas con console.error:")
for line_num, line_content in error_lines:
    print(f"Línea {line_num}: {line_content[:150]}")

# También buscar console.log para ver mensajes de depuración
print("\n\nBuscando console.log para ver mensajes de inicialización...")
log_lines = []
for i, line in enumerate(lines):
    if 'console.log' in line and 'Dashboard' in line:
        log_lines.append((i+1, line.strip()))
        
for line_num, line_content in log_lines[:10]:  # Mostrar solo primeros 10
    print(f"Línea {line_num}: {line_content[:150]}")

# Buscar el script de inicialización
print("\n\nBuscando el bloque de inicialización DOMContentLoaded...")
for i, line in enumerate(lines):
    if 'DOMContentLoaded' in line:
        print(f"Línea {i+1}: {line.strip()[:100]}")
        # Mostrar algunas líneas después
        for j in range(i, min(i+10, len(lines))):
            print(f"  {j+1}: {lines[j].strip()[:100]}")

# Buscar la función renderTableBatch
print("\n\nBuscando función renderTableBatch...")
for i, line in enumerate(lines):
    if 'function renderTableBatch' in line or 'renderTableBatch()' in line:
        print(f"Línea {i+1}: {line.strip()[:100]}")
        # Mostrar contexto
        start = max(0, i-5)
        end = min(len(lines), i+10)
        for j in range(start, end):
            prefix = ">>> " if j == i else "    "
            print(f"{prefix}{j+1}: {lines[j].strip()[:100]}")