import sys
sys.path.insert(0, 'webapp')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

# Consultar PropiedadRaw con coordenadas y precio
local_props = PropiedadRaw.objects.filter(
    coordenadas__isnull=False,
    precio_usd__isnull=False,
    precio_usd__gt=0
).exclude(coordenadas='')[:10]

print(f"PropiedadRaw encontradas: {local_props.count()}")
for p in local_props:
    print(f"  ID: {p.id}, coordenadas: {p.coordenadas}, precio: {p.precio_usd}")

# Consultar PropifaiProperty con coordenadas y precio
propifai_props = PropifaiProperty.objects.filter(
    coordinates__isnull=False,
    price__isnull=False,
    price__gt=0
).exclude(coordinates='')[:10]

print(f"PropifaiProperty encontradas: {propifai_props.count()}")
for p in propifai_props:
    print(f"  ID: {p.id}, coordenadas: {p.coordinates}, precio: {p.price}")