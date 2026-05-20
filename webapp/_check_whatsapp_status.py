import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from whatsapp_extractor.models import ArchivoExtraccionWhatsApp, ExtractorLog

archivos = ArchivoExtraccionWhatsApp.objects.all().order_by('-id')
lines = [f'TOTAL ARCHIVOS: {archivos.count()}']
for a in archivos:
    logs = ExtractorLog.objects.filter(archivo_subido=a).order_by('-id')
    if logs:
        log_info = ' | '.join([f'Log#{l.id}: estado={l.estado} extraidos={l.mensajes_extraidos_total} validos={l.mensajes_validos}' for l in logs])
    else:
        log_info = 'SIN LOGS'
    lines.append(f'ID={a.id} proc={a.procesado} nom="{a.nombre_archivo_original[:70]}" | {log_info}')

output = '\n'.join(lines)
print(output)

# Also write to file
with open('_whatsapp_status.txt', 'w', encoding='utf-8') as f:
    f.write(output + '\n')
