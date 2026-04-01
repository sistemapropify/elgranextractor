#!/usr/bin/env python
"""
Verificar que la columna "Fecha de creación" aparece en el dashboard.
"""
import requests
import re

try:
    resp = requests.get('http://127.0.0.1:8000/propifai/dashboard/calidad/', timeout=10)
    if resp.status_code == 200:
        print(f"Dashboard cargado (status {resp.status_code})")
        content = resp.text
        # Verificar que el encabezado "Fecha de creación" esté presente
        if 'Fecha de creación' in content:
            print("OK - Encabezado 'Fecha de creación' encontrado")
        else:
            print("WARNING - Encabezado no encontrado")
        # Buscar fechas en formato dd/mm/yyyy (patrón simple)
        fecha_pattern = r'\b\d{2}/\d{2}/\d{4}\b'
        fechas = re.findall(fecha_pattern, content)
        if fechas:
            print(f"OK - Fechas encontradas (ejemplo: {fechas[0]})")
        else:
            print("WARNING - No se encontraron fechas en formato dd/mm/yyyy")
        # Verificar que no haya errores de template
        if 'Error' in content or 'exception' in content.lower():
            print("ERROR - Posible error en template")
        else:
            print("OK - Sin errores aparentes")
    else:
        print(f"Error: status {resp.status_code}")
except Exception as e:
    print(f"Error al conectar: {e}")