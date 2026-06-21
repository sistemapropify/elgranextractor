#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug del parser - escribe a archivo para evitar problemas de encoding"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

# Redirigir stderr a nul
devnull = open(os.devnull, 'w')
old_stderr = sys.stderr
sys.stderr = devnull

import django
django.setup()

from whatsapp_extractor.services.whatsapp_txt_parser import WhatsAppTxtParser

# Restaurar stderr
sys.stderr = old_stderr
devnull.close()

output = []

linea = '[11/05/26, 7:16:03\u202fa.\u202fm.] Alejandra Ayala: Buenos dias'
output.append(f"LINEA: {repr(linea[:80])}")

patron3 = WhatsAppTxtParser.PATRON_FORMATO_3
output.append(f"PATRON: {patron3.pattern}")

match = patron3.match(linea)
if match:
    output.append(f"MATCH: groups={match.groups()}")
    output.append(f"  G1: {repr(match.group(1))}")
    output.append(f"  G2: {repr(match.group(2))}")
    output.append(f"  G3: {repr(match.group(3))}")
else:
    output.append("NO MATCH directo")
    # Intentar sin u202f
    linea2 = linea.replace('\u202f', ' ')
    output.append(f"SIN_U202F: {repr(linea2[:80])}")
    match2 = patron3.match(linea2)
    if match2:
        output.append(f"MATCH2: groups={match2.groups()}")
    else:
        output.append("NO MATCH2")
    
    # Intentar con _match_timestamp
    result = WhatsAppTxtParser._match_timestamp(linea)
    if result:
        output.append(f"_match_timestamp: {result}")
    else:
        output.append("_match_timestamp: NO MATCH")

# Probar con el archivo real
ruta = r"d:\proyectos\prometeo\webapp\media\whatsapp_extracciones\Chat de WhatsApp de EXITO INMOBILIARIO AGENTES.txt"
if os.path.exists(ruta):
    output.append(f"\nARCHIVO REAL: {ruta}")
    output.append(f"TAMANO: {os.path.getsize(ruta)} bytes")
    
    # Leer primeras 5 lineas
    with open(ruta, 'r', encoding='utf-8') as f:
        lines = [f.readline() for _ in range(5)]
    
    for i, line in enumerate(lines):
        output.append(f"\nLINEA {i}: {repr(line[:120])}")
        result = WhatsAppTxtParser._match_timestamp(line)
        if result:
            output.append(f"  MATCH: formato={result[0]}, timestamp={repr(result[1])}, resto={repr(result[2][:80])}")
            fecha = WhatsAppTxtParser._parsear_fecha_hora(result[1])
            output.append(f"  FECHA: {fecha}")
        else:
            output.append(f"  NO MATCH")
else:
    output.append(f"\nARCHIVO NO EXISTE: {ruta}")

# Escribir resultado
with open(r'd:\proyectos\prometeo\webapp\_debug_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("OK - output escrito a _debug_output.txt")
