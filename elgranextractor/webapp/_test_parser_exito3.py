"""Test: depurar _parsear_fecha_hora con el timestamp real."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django
django.setup()

import re
from datetime import datetime

OUT = r'd:\proyectos\prometeo\webapp\_debug_parser_test3.txt'

# El timestamp exacto capturado por el regex
ts = '11/05/26, 7:16:03\u202fa.\u202fm.'

with open(OUT, 'w', encoding='utf-8') as out:
    out.write(f'timestamp original: {repr(ts)}\n\n')
    
    # Paso 1: reemplazar \u202f por espacio
    paso1 = re.sub(r'[\u202f]', ' ', ts)
    out.write(f'Paso 1 (\\u202f -> space): {repr(paso1)}\n')
    
    # Paso 2: quitar coma después del año
    paso2 = re.sub(r'(\d{1,4}),\s+', r'\1 ', paso1)
    out.write(f'Paso 2 (quitar coma): {repr(paso2)}\n')
    
    # Paso 3: convertir a. m. -> AM
    paso3 = re.sub(r'\s*a\s*\.\s*m\s*', ' AM', paso2, flags=re.IGNORECASE)
    out.write(f'Paso 3 (a.m. -> AM): {repr(paso3)}\n')
    
    # Paso 4: convertir p. m. -> PM
    paso4 = re.sub(r'\s*p\s*\.\s*m\s*', ' PM', paso3, flags=re.IGNORECASE)
    out.write(f'Paso 4 (p.m. -> PM): {repr(paso4)}\n')
    
    paso4 = paso4.strip()
    out.write(f'Paso 5 (strip): {repr(paso4)}\n')
    
    # Intentar parsear
    try:
        dt = datetime.strptime(paso4, '%d/%m/%y %I:%M:%S %p')
        out.write(f'✅ PARSEADO: {dt.isoformat()}\n')
    except ValueError as e:
        out.write(f'❌ Error: {e}\n')
    
    # Probar con formato sin AM/PM
    out.write('\n--- Sin AM/PM ---\n')
    ts2 = '11/05/26, 7:16:03'
    paso2b = re.sub(r'(\d{1,4}),\s+', r'\1 ', ts2)
    out.write(f'limpio: {repr(paso2b)}\n')
    try:
        dt = datetime.strptime(paso2b, '%d/%m/%y %H:%M:%S')
        out.write(f'✅ PARSEADO: {dt.isoformat()}\n')
    except ValueError as e:
        out.write(f'❌ Error: {e}\n')
    
    # Probar con AM/PM normal
    out.write('\n--- AM/PM normal ---\n')
    ts3 = '11/05/26, 7:16:03 AM'
    paso3b = re.sub(r'(\d{1,4}),\s+', r'\1 ', ts3)
    out.write(f'limpio: {repr(paso3b)}\n')
    try:
        dt = datetime.strptime(paso3b, '%d/%m/%y %I:%M:%S %p')
        out.write(f'✅ PARSEADO: {dt.isoformat()}\n')
    except ValueError as e:
        out.write(f'❌ Error: {e}\n')

print(f'Test escrito en {OUT}')
