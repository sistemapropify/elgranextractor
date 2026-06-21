"""
Diagnóstico rápido del extractor WhatsApp.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from whatsapp_extractor.models import ArchivoExtraccionWhatsApp, ExtractorLog, LogEntry

print("=" * 60)
print("ARCHIVOS DE EXTRACCIÓN")
print("=" * 60)
archivos = ArchivoExtraccionWhatsApp.objects.all().order_by('-fecha_subida')
print(f"Total: {archivos.count()}")
for a in archivos:
    print(f"  ID={a.id}")
    print(f"  Nombre: {a.nombre_archivo_original}")
    print(f"  Procesado: {a.procesado}")
    print(f"  Grupo relacionado ID: {a.grupo_relacionado_id}")
    print(f"  Ruta: {a.ruta_almacenamiento}")
    print(f"  Existe: {os.path.exists(a.ruta_almacenamiento)}")
    print()

print("=" * 60)
print("LOGS DE EXTRACCIÓN (últimos 10)")
print("=" * 60)
logs = ExtractorLog.objects.all().order_by('-ejecucion_fecha')[:10]
print(f"Total logs: {ExtractorLog.objects.count()}")
for l in logs:
    print(f"  ID={l.id}")
    print(f"  Estado: {l.estado}")
    print(f"  Archivo: {l.archivo_subido}")
    print(f"  Extraídos: {l.mensajes_extraidos_total}")
    print(f"  Válidos: {l.mensajes_validos}")
    print(f"  Duplicados: {l.requerimientos_duplicados}")
    # Últimas entradas de log
    entries = LogEntry.objects.filter(extractor_log=l).order_by('-timestamp')[:3]
    for e in entries:
        print(f"    [{e.nivel}] {e.mensaje[:100]}")
    print()

print("=" * 60)
print("GRUPOS WHATSAPP CONFIGURADOS")
print("=" * 60)
from whatsapp_extractor.models import WhatsappGroupSession
grupos = WhatsappGroupSession.objects.all()
print(f"Total: {grupos.count()}")
for g in grupos:
    print(f"  ID={g.id} | {g.nombre_grupo} | activo={g.activo} | fuente={g.fuente_choice}")
