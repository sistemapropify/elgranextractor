"""
Borra TODOS los registros de Requerimiento para empezar de cero.
Los nuevos procesamientos usarán el código corregido que:
1. Guarda la fecha real del mensaje WhatsApp (desde fecha_hora del parser)
2. Incluye el agente en la deduplicación
3. Busca en TODOS los requerimientos sin filtro de fecha
"""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DATABASE_URL'] = 'mssql://prometeo_user:Prometeo2025*@prometeo-db.database.windows.net:1433/prometeo_db'
sys.path.insert(0, os.path.dirname(__file__))
import django; django.setup()

from requerimientos.models import Requerimiento

total = Requerimiento.objects.count()
print(f'Total Requerimiento a borrar: {total}')

# Borrar en lotes para no sobrecargar la BD
borrados = 0
lote = 500
while True:
    ids = list(Requerimiento.objects.values_list('pk', flat=True)[:lote])
    if not ids:
        break
    Requerimiento.objects.filter(pk__in=ids).delete()
    borrados += len(ids)
    print(f'  Borrados: {borrados}/{total}')

print(f'Total borrados: {borrados}')
print(f'Quedan: {Requerimiento.objects.count()}')
