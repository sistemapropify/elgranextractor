import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DATABASE_URL'] = 'mssql://prometeo_user:Prometeo2025*@prometeo-db.database.windows.net:1433/prometeo_db'
import django; django.setup()
from requerimientos.models import Requerimiento
from whatsapp_extractor.models import ExtractorLog

total_con_log = Requerimiento.objects.filter(extractor_log__isnull=False).count()
total_sin_log = Requerimiento.objects.filter(extractor_log__isnull=True).count()
print(f'Con extractor_log: {total_con_log}')
print(f'Sin extractor_log: {total_sin_log}')
for log in ExtractorLog.objects.all().order_by('-id')[:5]:
    print(f'Log ID={log.id}: estado={log.estado}, fecha={log.ejecucion_fecha}, msgs={log.mensajes_extraidos_total}')
