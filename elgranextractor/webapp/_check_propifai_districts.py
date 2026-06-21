import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

from propifai.models import PropifaiProperty
from django.db.models import Count

distritos = PropifaiProperty.objects.values('district').annotate(total=Count('id')).order_by('-total')
print("=== PROPIEDADES POR DISTRITO ===")
for d in distritos:
    print(f'{d["district"]}: {d["total"]} propiedades')

print("\n=== PROPIEDADES EN YANAHUARA ===")
yanahuara = PropifaiProperty.objects.filter(district__icontains='yanahuara')
print(f'Total: {yanahuara.count()}')
for p in yanahuara[:10]:
    print(f'  ID={p.id}, titulo={p.titulo}, precio={p.precio_venta}, district={p.district}')

print("\n=== TOTAL GENERAL ===")
print(f'Total propiedades: {PropifaiProperty.objects.count()}')
