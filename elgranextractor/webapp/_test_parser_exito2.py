"""Test: verificar que los cambios al parser funcionan para Éxito Inmobiliario."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django
django.setup()

from whatsapp_extractor.services.whatsapp_txt_parser import WhatsAppTxtParser

OUT = r'd:\proyectos\prometeo\webapp\_debug_parser_test2.txt'

lineas_reales = [
    '[11/05/26, 7:16:03\u202fa.\u202fm.] Alejandra Ayala Agente Inmobiliario: Buenos dias con todos',
    '[11/05/26, 9:16:58\u202fa.\u202fm.] Alejandra Ayala Agente Inmobiliario: 🔎 REQUERIMIENTO – CLIENTE DIRECTO',
    '[11/05/26, 9:16:59\u202fa.\u202fm.] Alejandra Ayala Agente Inmobiliario: 🔎 REQUERIMIENTO DE CLIENTE DIRECTO – ANTICRESIS',
    '[11/05/26, 9:16:59\u202fa.\u202fm.] Otro Agente: Test mensaje',
]

with open(OUT, 'w', encoding='utf-8') as out:
    out.write('=== TEST 1: Match individual de cada línea ===\n\n')
    
    for i, linea in enumerate(lineas_reales):
        out.write(f'Línea {i}: {repr(linea[:100])}\n')
        match = WhatsAppTxtParser._match_timestamp(linea)
        if match:
            ts, autor, texto = match
            out.write(f'  ✅ MATCH!\n')
            out.write(f'  timestamp_str={repr(ts)}\n')
            fecha_hora = WhatsAppTxtParser._parsear_fecha_hora(ts)
            out.write(f'  fecha_hora_iso={repr(fecha_hora)}\n')
            out.write(f'  autor={repr(autor)}\n')
            out.write(f'  texto={repr(texto[:80])}\n')
        else:
            out.write(f'  ❌ NO MATCH\n')
        out.write('\n')
    
    out.write('=== TEST 2: Parseo completo del archivo real ===\n\n')
    
    ruta_real = r'D:\proyectos\prometeo\webapp\media\whatsapp_extracciones\6a7bbb117912404ca72237e8552ea550_Chat de WhatsApp de EXITO INMOBILIARIO AGENTES.txt'
    
    if os.path.exists(ruta_real):
        try:
            mensajes = WhatsAppTxtParser.parsear_archivo(ruta_real)
            out.write(f'Total mensajes parseados: {len(mensajes)}\n\n')
            for i, msg in enumerate(mensajes[:10]):
                out.write(f'Mensaje {i+1}:\n')
                out.write(f'  autor={repr(msg["autor"])}\n')
                out.write(f'  fecha={repr(msg["fecha"])}\n')
                out.write(f'  hora={repr(msg["hora"])}\n')
                out.write(f'  texto={repr(msg["texto"][:100])}\n\n')
        except Exception as e:
            out.write(f'ERROR: {e}\n')
    else:
        out.write(f'Archivo no encontrado: {ruta_real}\n')

print(f'Test escrito en {OUT}')
