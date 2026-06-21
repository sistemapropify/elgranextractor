# -*- coding: utf-8 -*-
"""
Script para resetear archivos/estados y procesar directamente.
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from whatsapp_extractor.models import ArchivoExtraccionWhatsApp, ExtractorLog
from whatsapp_extractor.tasks import procesar_archivo_extraccion

# 1. Resetear logs stuck
print("=== RESETEANDO LOGS STUCK ===")
stuck_logs = ExtractorLog.objects.filter(estado__in=['En progreso', 'running'])
print(f"Logs stuck encontrados: {stuck_logs.count()}")
for l in stuck_logs:
    l.estado = 'error'
    l.mensaje_error = 'Reiniciado - proceso anterior quedo pegado'
    l.save()
    print(f"  Log ID={l.id} => marcado como error")

# 2. Resetear archivos no procesados
print()
print("=== RESETEANDO ARCHIVOS ===")
archivos = ArchivoExtraccionWhatsApp.objects.filter(procesado=False).order_by('-fecha_subida')
print(f"Archivos no procesados: {archivos.count()}")
for a in archivos:
    print(f"  ID={a.id} | {a.nombre_archivo_original} | tam={a.tamanio_kb}KB")

# 3. Procesar el mas reciente (ID=10)
if archivos.exists():
    archivo = archivos.first()
    print()
    print(f"=== INICIANDO PROCESAMIENTO DEL ARCHIVO ID={archivo.id} ===")
    print(f"Nombre: {archivo.nombre_archivo_original}")
    print(f"Ruta: {archivo.ruta_almacenamiento}")
    print()
    print("Esto puede tomar varios minutos...")
    print()
    
    resultado = procesar_archivo_extraccion(archivo.id)
    
    print()
    print("=== RESULTADO ===")
    for k, v in resultado.items():
        print(f"  {k}: {v}")
else:
    print("No hay archivos para procesar.")
