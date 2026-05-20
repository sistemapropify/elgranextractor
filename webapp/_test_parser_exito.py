"""Test: verificar por qué el parser no reconoce el formato de Éxito Inmobiliario."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django
django.setup()

import re
from whatsapp_extractor.services.whatsapp_txt_parser import WhatsAppTxtParser

OUT = r'd:\proyectos\prometeo\webapp\_debug_parser_test.txt'

linea_real = '[11/05/26, 7:16:03\u202fa.\u202fm.] Alejandra Ayala Agente Inmobiliario: Buenos dias con todos'

with open(OUT, 'w', encoding='utf-8') as out:
    out.write(f'LINEA REAL: {repr(linea_real)}\n\n')
    
    for nombre, patron in WhatsAppTxtParser.PATRONES:
        match = patron.match(linea_real)
        out.write(f'Patron {nombre}: {patron.pattern}\n')
        if match:
            out.write(f'  ✅ MATCH!\n')
            out.write(f'  group(1)={repr(match.group(1))}\n')
            out.write(f'  group(2)={repr(match.group(2))}\n')
            out.write(f'  group(3)={repr(match.group(3))}\n')
        else:
            out.write(f'  ❌ NO MATCH\n')
        out.write('\n')
    
    # Probar con PATRON_FORMATO_3 modificado
    out.write('--- PRUEBAS CON PATRONES MODIFICADOS ---\n\n')
    
    # Test 1: Agregar coma opcional despuÃ©s del aÃ±o
    patron_test1 = re.compile(
        r'^\[(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*(.*)',
        re.UNICODE
    )
    match = patron_test1.match(linea_real)
    out.write(f'Test 1 (coma opcional):\n')
    if match:
        out.write(f'  ✅ MATCH! timestamp={repr(match.group(1))}\n')
        ts = match.group(1).strip()
        out.write(f'  timestamp_stripped={repr(ts)}\n')
    else:
        out.write(f'  ❌ NO MATCH\n')
    out.write('\n')
    
    # Test 2: Capturar todo dentro de corchetes (mÃ¡s permisivo)
    patron_test2 = re.compile(
        r'^\[([^\]]+)\]\s*([^:]+):\s*(.*)',
        re.UNICODE
    )
    match = patron_test2.match(linea_real)
    out.write(f'Test 2 (capturar todo dentro de []):\n')
    if match:
        out.write(f'  ✅ MATCH! timestamp={repr(match.group(1))}\n')
        ts = match.group(1).strip()
        out.write(f'  timestamp_stripped={repr(ts)}\n')
        # Probar _parsear_fecha_hora con este timestamp
        result = WhatsAppTxtParser._parsear_fecha_hora(ts)
        out.write(f'  _parsear_fecha_hora result={repr(result)}\n')
    else:
        out.write(f'  ❌ NO MATCH\n')
    out.write('\n')
    
    # Test 3: Parsear fecha_hora con timestamp limpio
    out.write('--- PRUEBAS _parsear_fecha_hora ---\n\n')
    
    timestamps_test = [
        '11/05/26, 7:16:03\u202fa.\u202fm.',  # Original con espacio fino
        '11/05/26, 7:16:03 a. m.',             # Con espacio normal
        '11/05/26, 7:16:03 AM',                # Sin puntos
        '11/05/26 7:16:03',                    # Sin coma ni AM/PM
        '11/05/26 7:16',                       # Sin segundos
    ]
    
    for ts in timestamps_test:
        out.write(f'  timestamp={repr(ts)}\n')
        result = WhatsAppTxtParser._parsear_fecha_hora(ts)
        out.write(f'  result={repr(result)}\n\n')

print(f'Test escrito en {OUT}')
