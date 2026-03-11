import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
try:
    django.setup()
except Exception as e:
    print(f"Error setup: {e}")
    sys.exit(1)

from requerimientos.models import Requerimiento
from django.db.models import Count

print(f"Total requerimientos: {Requerimiento.objects.count()}")

fuentes = Requerimiento.objects.values_list('fuente', flat=True).distinct()
print("Fuentes únicas:", list(fuentes))

print("\nConteo por fuente:")
for fuente, count in Requerimiento.objects.values('fuente').annotate(total=Count('id')).order_by('-total'):
    print(f"  {fuente}: {count}")

# Verificar algunos registros recién importados
print("\nAlgunos registros recientes:")
for r in Requerimiento.objects.order_by('-id')[:5]:
    print(f"  ID {r.id}: fuente='{r.fuente}', agente='{r.agente[:20]}', fecha={r.fecha}")