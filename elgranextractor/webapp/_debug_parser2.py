#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug detallado de _match_timestamp"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

devnull = open(os.devnull, 'w')
old_stderr = sys.stderr
sys.stderr = devnull

import django
django.setup()

sys.stderr = old_stderr
devnull.close()

from whatsapp_extractor.services.whatsapp_txt_parser import WhatsAppTxtParser

output = []

linea = '[11/05/26, 7:16:03\u202fa.\u202fm.] Alejandra Ayala: Buenos dias'
output.append(f"LINEA: {repr(linea[:80])}")
output.append("")

# Probar CADA patron individualmente
for nombre, patron in WhatsAppTxtParser.PATRONES:
    match = patron.match(linea)
    if match:
        output.append(f"[{nombre}] MATCH: groups={match.groups()}")
        output.append(f"  G1: {repr(match.group(1))}")
        output.append(f"  G2: {repr(match.group(2))}")
        output.append(f"  G3: {repr(match.group(3))}")
    else:
        output.append(f"[{nombre}] NO MATCH")

output.append("")
output.append("--- _match_timestamp result ---")
result = WhatsAppTxtParser._match_timestamp(linea)
if result:
    output.append(f"  timestamp_str={repr(result[0])}")
    output.append(f"  autor={repr(result[1])}")
    output.append(f"  texto={repr(result[2])}")
else:
    output.append("  NO MATCH")

with open(r'd:\proyectos\prometeo\webapp\_debug_output2.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("OK")
