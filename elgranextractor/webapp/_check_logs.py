import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from whatsapp_extractor.models import ExtractorLog

logs = ExtractorLog.objects.all().order_by('-id')
with open('_logs_output.txt', 'w', encoding='utf-8') as f:
    f.write(f'TOTAL LOGS: {logs.count()}\n')
    for l in logs:
        f.write(f'Log#{l.id}: archivo_subido="{l.archivo_subido}" grupo_id={l.grupo_asociado_id} estado={l.estado} extraidos={l.mensajes_extraidos_total} validos={l.mensajes_validos} nuevos={l.requerimientos_nuevos} duplicados={l.requerimientos_duplicados}\n')
print('OK')
