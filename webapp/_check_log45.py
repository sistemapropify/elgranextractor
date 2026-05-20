import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from whatsapp_extractor.models import ExtractorLog, LogEntry

log = ExtractorLog.objects.get(id=45)
entries = LogEntry.objects.filter(extractor_log=log).order_by('id')

with open('_log45_detail.txt', 'w', encoding='utf-8') as f:
    f.write(f'Log#45: estado={log.estado} extraidos={log.mensajes_extraidos_total} validos={log.mensajes_validos} nuevos={log.requerimientos_nuevos} duplicados={log.requerimientos_duplicados}\n')
    f.write(f'Total entries: {entries.count()}\n\n')
    for e in entries:
        f.write(f'Entry#{e.id}: nivel={e.nivel} timestamp={e.timestamp}\n')
        f.write(f'  mensaje: {e.mensaje[:300]}\n')
        if e.detalles:
            f.write(f'  detalles: {str(e.detalles)[:400]}\n')
        f.write('---\n')

print('OK')
