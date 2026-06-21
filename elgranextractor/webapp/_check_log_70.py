import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from whatsapp_extractor.models import ExtractorLog, LogEntry

log = ExtractorLog.objects.get(id=70)
print(f'=== EXTRACTOR LOG 70 ===')
print(f'estado: {log.estado}')
print(f'mensajes_total: {log.mensajes_total}')
print(f'mensajes_validos: {log.mensajes_validos}')
print(f'mensajes_duplicados: {log.mensajes_duplicados}')
print(f'fecha_inicio: {log.fecha_inicio}')
print(f'fecha_fin: {log.fecha_fin}')
print()

entries = LogEntry.objects.filter(extractor_log=log).order_by('-id')[:5]
print('=== ULTIMOS 5 LOG ENTRIES ===')
for e in entries:
    print(f'ID={e.id} nivel={e.nivel} mensaje={e.mensaje[:80]} progreso={e.progreso} total={e.total_mensajes} validos={e.validos} duplicados={e.duplicados}')
print()

total = LogEntry.objects.filter(extractor_log=log).count()
print(f'Total entries: {total}')
