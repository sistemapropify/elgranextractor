"""
Script unico para limpiar el log #7 (fallido por piso_preferencia NULL)
y dejar el archivo listo para reprocesar.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from whatsapp_extractor.models import ExtractorLog, LogEntry, ArchivoExtraccionWhatsApp
from requerimientos.models import Requerimiento

LOG_ID = 7

try:
    log = ExtractorLog.objects.get(pk=LOG_ID)
except ExtractorLog.DoesNotExist:
    print('ERROR: Log #%d no existe.' % LOG_ID)
    sys.exit(1)

print('Log #%d: estado=%s, validos=%s, duplicados=%s' % (
    LOG_ID, log.estado, log.mensajes_validos, log.requerimientos_duplicados))

# 1. Buscar el archivo asociado
archivo = ArchivoExtraccionWhatsApp.objects.filter(log_asociado=log).first()
if archivo:
    print('Archivo asociado: %s (ID=%d)' % (archivo.nombre_archivo_original, archivo.id))
else:
    print('No se encontro archivo asociado a este log.')
    archivos = ArchivoExtraccionWhatsApp.objects.filter(
        nombre_archivo_original__icontains='RED INMOBILIARIA'
    )
    if archivos.exists():
        archivo = archivos.first()
        print('Encontrado por nombre: %s (ID=%d)' % (archivo.nombre_archivo_original, archivo.id))

# 2. Eliminar Requerimientos asociados
reqs = Requerimiento.objects.filter(extractor_log=log)
print('Eliminando %d requerimientos...' % reqs.count())
reqs.delete()

# 3. Eliminar LogEntries
entries = LogEntry.objects.filter(extractor_log=log)
print('Eliminando %d log entries...' % entries.count())
entries.delete()

# 4. Eliminar el log
log.delete()
print('Log #%d eliminado.' % LOG_ID)

# 5. Resetear archivo
if archivo:
    archivo.procesado = False
    archivo.log_asociado = None
    archivo.save()
    print('Archivo "%s" reseteado a NO procesado.' % archivo.nombre_archivo_original)
    print('Ve a http://localhost:8000/whatsapp-extractor/archivo/%d/ para reprocesar.' % archivo.id)
else:
    print('No se pudo resetear archivo.')
