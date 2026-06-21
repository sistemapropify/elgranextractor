import sys, os
sys.path.insert(0, 'd:\\proyectos\\prometeo\\webapp')
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from propifai.models import PropifaiProperty
from requerimientos.models import Requerimiento

req = Requerimiento.objects.get(id=20263)
print('Requerimiento 20263:')
print(f'  presupuesto_monto: {req.presupuesto_monto}')
print(f'  presupuesto_moneda: {req.presupuesto_moneda}')
print(f'  distritos: {req.distritos}')
print(f'  tipo_propiedad: {req.tipo_propiedad}')
print()

props = PropifaiProperty.objects.filter(code='PROP000048')
for p in props:
    print(f'Propiedad {p.code}:')
    print(f'  price: {p.price}')
    print(f'  currency_id: {p.currency_id}')
    print(f'  district: {p.district}')
    print(f'  title: {p.title}')
    print(f'  bedrooms: {p.bedrooms}')
    print(f'  bathrooms: {p.bathrooms}')
    print()

# Also check what the API returns
from matching.serializers import PropiedadSimpleSerializer
ser = PropiedadSimpleSerializer(p)
print('Serializer data:')
for k, v in ser.data.items():
    print(f'  {k}: {v}')
