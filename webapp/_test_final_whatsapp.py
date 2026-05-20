#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test final del WhatsApp Extractor - parser + PATRON_NOMBRE_GRUPO"""
import sys, os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django
django.setup()

from whatsapp_extractor.tasks import PATRON_NOMBRE_GRUPO, _limpiar_nombre_grupo
from whatsapp_extractor.services.whatsapp_txt_parser import WhatsAppTxtParser

def safe(text):
    if isinstance(text, str):
        return text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    return str(text)

# ============================================================
# TEST 1: PATRON_NOMBRE_GRUPO generico
# ============================================================
print("=" * 70)
print("TEST 1: PATRON_NOMBRE_GRUPO (debe aceptar cualquier formato)")
print("=" * 70)

test_names = [
    ('Chat de WhatsApp con RED INMOBILIARIA AREQUIPA.txt', 'RED INMOBILIARIA AREQUIPA'),
    ('Chat de WhatsApp de EXITO INMOBILIARIO AGENTES.txt', 'EXITO INMOBILIARIO AGENTES'),
    ('Chat de WhatsApp por GRUPO VENTAS.txt', 'GRUPO VENTAS'),
    ('WhatsApp Chat with ENGLISH GROUP.txt', 'ENGLISH GROUP'),
    ('Chat WhatsApp - Grupo Ejemplo.txt', 'Grupo Ejemplo'),
    ('Chat de WhatsApp del GRUPO TEST.txt', 'GRUPO TEST'),
    ('Chat de WhatsApp en MI GRUPO.txt', 'MI GRUPO'),
    ('WhatsApp Chat GROUP NAME.txt', 'GROUP NAME'),
    ('Chat de WhatsApp para CLIENTES VIP.txt', 'CLIENTES VIP'),
    ('Chat de WhatsApp desde OFICINA CENTRAL.txt', 'OFICINA CENTRAL'),
]

all_ok = True
for name, expected in test_names:
    match = PATRON_NOMBRE_GRUPO.search(name)
    if match:
        raw = match.group(1).strip()
        extracted = _limpiar_nombre_grupo(raw)
        status = 'OK' if extracted == expected else 'MISMATCH'
        if extracted != expected:
            all_ok = False
        print(f"  [{status}] {safe(name)}")
        print(f"       raw='{raw}' -> '{extracted}' (esperado: '{expected}')")
    else:
        print(f"  [FAIL] {safe(name)} -> NO MATCH")
        all_ok = False

print()

# ============================================================
# TEST 2: Parser con formatos iOS
# ============================================================
print("=" * 70)
print("TEST 2: Parser - formatos iOS con coma, segundos y AM/PM con puntos")
print("=" * 70)

test_lines = [
    ('[11/05/26, 7:16:03\u202fa.\u202fm.] Alejandra Ayala: Buenos dias', '2026-05-11T07:16:03', 'Alejandra Ayala'),
    ('[11/05/26, 7:16:03 p. m.] Otro Usuario: Mensaje de prueba', '2026-05-11T19:16:03', 'Otro Usuario'),
    ('[15/01/2024, 10:30:45\u202fa.\u202fm.] Test User: Hola mundo', '2024-01-15T10:30:45', 'Test User'),
    ('[15/01/2024, 10:30:45 p. m.] Test User: Mensaje nocturno', '2024-01-15T22:30:45', 'Test User'),
    ('[12/6/24, 10:51] Usuario: Test sin segundos', '2024-12-06T10:51:00', 'Usuario'),
    ('[12/06/2024, 10:51:30] Usuario: Test', '2024-06-12T10:51:30', 'Usuario'),
    ('2024-01-15 14:30 - Juan Perez: Mensaje android', '2024-01-15T14:30:00', 'Juan Perez'),
    ('15/01/2024, 2:30 PM - Maria Lopez: Hola', '2024-01-15T14:30:00', 'Maria Lopez'),
]

all_ok2 = True
for linea, expected_fecha, expected_autor in test_lines:
    resultado = WhatsAppTxtParser._match_timestamp(linea)
    if resultado:
        # _match_timestamp devuelve (timestamp_str, autor, texto)
        timestamp_str, autor, texto = resultado
        fecha_iso = WhatsAppTxtParser._parsear_fecha_hora(timestamp_str)
        
        fecha_ok = fecha_iso == expected_fecha
        autor_ok = autor == expected_autor
        
        if fecha_ok and autor_ok:
            print(f"  [OK] {autor}")
            print(f"       {safe(timestamp_str)} -> {fecha_iso}")
        else:
            all_ok2 = False
            print(f"  [FAIL]")
            print(f"       Timestamp: '{safe(timestamp_str)}' -> '{fecha_iso}' (esperado: '{expected_fecha}')")
            print(f"       Autor: '{autor}' (esperado: '{expected_autor}')")
    else:
        all_ok2 = False
        print(f"  [FAIL] '{safe(linea[:70])}...' -> NO MATCH")

print()

# ============================================================
# TEST 3: Parseo completo del archivo real de Exito Inmobiliario
# ============================================================
print("=" * 70)
print("TEST 3: Parseo completo del archivo real de EXITO INMOBILIARIO")
print("=" * 70)

ruta_exito = r"d:\proyectos\prometeo\webapp\media\whatsapp_extracciones\Chat de WhatsApp de EXITO INMOBILIARIO AGENTES.txt"
if os.path.exists(ruta_exito):
    mensajes = WhatsAppTxtParser.parsear_archivo(ruta_exito)
    print(f"  Total mensajes parseados: {len(mensajes)}")
    if mensajes:
        print(f"  Primer: [{mensajes[0]['fecha_hora']}] {mensajes[0]['autor']}: {safe(mensajes[0]['texto'][:80])}")
        print(f"  Ultimo: [{mensajes[-1]['fecha_hora']}] {mensajes[-1]['autor']}: {safe(mensajes[-1]['texto'][:80])}")
        
        autores = set(m['autor'] for m in mensajes)
        print(f"  Autores unicos: {len(autores)}")
        for a in sorted(autores)[:5]:
            count = sum(1 for m in mensajes if m['autor'] == a)
            print(f"     - {a}: {count} mensajes")
        if len(autores) > 5:
            print(f"     ... y {len(autores)-5} mas")
else:
    print(f"  [WARN] Archivo no encontrado: {ruta_exito}")

print()
print("=" * 70)
if all_ok and all_ok2:
    print("TODOS LOS TESTS PASARON")
else:
    print("ALGUNOS TESTS FALLARON - Revisar output arriba")
print("=" * 70)
