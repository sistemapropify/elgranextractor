import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

obj = PropiedadRaw.objects.first()
if obj:
    print('Primer registro (ID: {}):'.format(obj.id))
    print('  Departamento:', obj.departamento)
    print('  Provincia:', obj.provincia)
    print('  Distrito:', obj.distrito)
    print('  Coordenadas:', obj.coordenadas)
    print('  Número de habitaciones:', obj.numero_habitaciones)
    print('  Número de baños:', obj.numero_banos)
    print('  Habitaciones (campo antiguo):', obj.habitaciones)
    print('  Baños (campo antiguo):', obj.banos)
    print('  Precio USD:', obj.precio_usd)
    print('  Tipo propiedad:', obj.tipo_propiedad)
    print('  URL propiedad:', obj.url_propiedad)
else:
    print('No hay registros')

# Contar registros con datos en esos campos
print('\nConteo de registros con datos:')
total = PropiedadRaw.objects.count()
print('  Total registros:', total)
for field in ['departamento', 'provincia', 'distrito', 'coordenadas', 'numero_habitaciones', 'numero_banos']:
    count = PropiedadRaw.objects.exclude(**{field: None}).count()
    print('  {}: {}'.format(field, count))