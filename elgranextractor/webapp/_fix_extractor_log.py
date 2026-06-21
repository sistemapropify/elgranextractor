"""
Script para arreglar ExtractorLogs atascados en 'running'
y diagnosticar consumo de DeepSeek.
"""
import os
import sys
import io

# Forzar UTF-8 para evitar errores de encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from whatsapp_extractor.models import ExtractorLog, EstadoExtraccionChoices, LogEntry

# 1. Arreglar TODOS los ExtractorLog en running
print("=" * 60)
print("ARREGLANDO EXTRACTORLOGS ATASCADOS EN 'RUNNING'")
print("=" * 60)

running_logs = ExtractorLog.objects.filter(estado='running')
print(f"Total ExtractorLog en running: {running_logs.count()}")

for log in running_logs:
    old_estado = log.estado
    log.estado = EstadoExtraccionChoices.COMPLETED
    if not log.tiempo_proceso_segundos:
        log.tiempo_proceso_segundos = 0
    log.save(update_fields=['estado', 'tiempo_proceso_segundos'])
    print(f"  Log {log.id}: {old_estado} -> {log.estado} (msgs: {log.mensajes_extraidos_total})")

# 2. Verificar si hay celery beat corriendo (tareas programadas)
print("\n" + "=" * 60)
print("TAREAS PERIODICAS CELERY BEAT")
print("=" * 60)

try:
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
    tasks = PeriodicTask.objects.filter(enabled=True)
    print(f"Tareas periodicas activas: {tasks.count()}")
    for task in tasks:
        if task.interval:
            print(f"  - {task.name} (cada {task.interval.period}/{task.interval.every})")
        elif task.crontab:
            print(f"  - {task.name} (crontab: {task.crontab})")
        else:
            print(f"  - {task.name} (sin schedule)")
except Exception as e:
    print(f"  No se pudo leer django_celery_beat: {e}")

# 3. Verificar si hay workers de celery activos
print("\n" + "=" * 60)
print("PROCESOS CELERY EN EL SISTEMA")
print("=" * 60)
import subprocess
try:
    result = subprocess.run(
        ['tasklist', '/V'],
        capture_output=True, text=True, timeout=5, shell=True
    )
    celery_procs = [l for l in result.stdout.split('\n') if 'celery' in l.lower()]
    if celery_procs:
        for p in celery_procs:
            print(f"  {p.strip()}")
    else:
        print("  No hay procesos celery corriendo")
except Exception as e:
    print(f"  Error: {e}")

# 4. Ver logs recientes del log 70
print("\n" + "=" * 60)
print("LOGS RECIENTES DEL EXTRACTORLOG 70")
print("=" * 60)
try:
    log70 = ExtractorLog.objects.get(id=70)
    ultimos = LogEntry.objects.filter(extractor_log=log70).order_by('-id')[:10]
    for entry in ultimos:
        msg = str(entry.mensaje)[:100] if entry.mensaje else ""
        print(f"  [{entry.nivel}] id={entry.id}: {msg}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTICO COMPLETADO")
print("=" * 60)
