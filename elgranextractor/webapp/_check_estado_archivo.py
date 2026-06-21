"""
Script temporal para verificar estado de archivos de extracción WhatsApp.
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from whatsapp_extractor.models import ArchivoExtraccionWhatsApp, ExtractorLog

print('=== ARCHIVOS DE EXTRACCIÓN ===')
for a in ArchivoExtraccionWhatsApp.objects.all().order_by('-fecha_subida')[:5]:
    print(f'ID={a.id} | nombre="{a.nombre_archivo_original}" | proc={a.procesado} | tam={a.tamanio_kb}KB')

print()
print('=== LOGS DE EXTRACCIÓN ===')
for l in ExtractorLog.objects.all().order_by('-ejecucion_fecha')[:5]:
    print(f'ID={l.id} | archivo="{l.archivo_subido[:60]}" | estado={l.estado} | extraidos={l.mensajes_extraidos_total} | validos={l.mensajes_validos} | nuevos={l.requerimientos_nuevos} | duplicados={l.requerimientos_duplicados} | basura={l.requerimientos_basura_filtrados} | error="{l.mensaje_error[:80] if l.mensaje_error else ""}"')

print()
print('=== REQUERIMIENTOS CREADOS POR EXTRACTOR ===')
from requerimientos.models import Requerimiento
ultimos = Requerimiento.objects.filter(extractor_log__isnull=False).order_by('-fecha_creacion')[:5]
print(f'Total requerimientos con extractor_log: {Requerimiento.objects.filter(extractor_log__isnull=False).count()}')
for r in ultimos:
    print(f'  ID={r.id} | req="{str(r.requerimiento)[:80]}" | fecha={r.fecha_creacion}')

print()
print('FIN - Script ejecutado correctamente')
