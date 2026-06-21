import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from requerimientos.models import Requerimiento
from whatsapp_extractor.models import ExtractorLog, LogEntry, ArchivoExtraccionWhatsApp

try:
    log = ExtractorLog.objects.get(id=6)
    print(f'Log 6 encontrado: estado={log.estado}')
    
    # Buscar archivo asociado via log_asociado FK
    archivo = ArchivoExtraccionWhatsApp.objects.filter(log_asociado=log).first()
    if archivo:
        print(f'Archivo asociado: ID={archivo.id}, nombre={archivo.nombre_archivo_original}')
    else:
        print('No se encontró archivo asociado a este log')
    
    # Eliminar Requerimientos
    reqs = Requerimiento.objects.filter(extractor_log=log)
    print(f'Requerimientos a eliminar: {reqs.count()}')
    reqs.delete()
    
    # Eliminar LogEntries
    entries = LogEntry.objects.filter(extractor_log=log)
    print(f'LogEntries a eliminar: {entries.count()}')
    entries.delete()
    
    # Eliminar el log
    log.delete()
    print('Log 6 eliminado')
    
    # Resetear archivo
    if archivo:
        archivo.procesado = False
        archivo.log_asociado = None
        archivo.save()
        print(f'Archivo {archivo.id} reseteado a NO procesado')
        print(f'Ve a http://127.0.0.1:8000/whatsapp-extractor/archivo/{archivo.id}/ y haz clic en "Procesar"')
except ExtractorLog.DoesNotExist:
    print('Log 6 no encontrado, puede que ya se haya eliminado')
except Exception as e:
    import traceback
    print(f'Error: {e}')
    traceback.print_exc()
