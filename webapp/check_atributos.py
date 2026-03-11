import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

total = PropiedadRaw.objects.count()
print('Total propiedades:', total)
con_atributos = PropiedadRaw.objects.exclude(atributos_extras={}).count()
print('Con atributos_extras no vacíos:', con_atributos)
if con_atributos > 0:
    p = PropiedadRaw.objects.exclude(atributos_extras={}).first()
    print('Ejemplo atributos_extras:', json.dumps(p.atributos_extras, indent=2, ensure_ascii=False))
    # Contar keys únicas
    keys = set()
    for prop in PropiedadRaw.objects.exclude(atributos_extras={}).only('atributos_extras'):
        if isinstance(prop.atributos_extras, dict):
            keys.update(prop.atributos_extras.keys())
    print('Keys únicas encontradas:', len(keys))
    print('Primeras 10:', sorted(list(keys))[:10])
else:
    print('No hay atributos_extras. Puede que ya se migraron a campos fijos.')
    # Verificar si hay campos dinámicos existentes
    from ingestas.models import CampoDinamico
    print('Campos dinámicos existentes:', CampoDinamico.objects.count())
    for cd in CampoDinamico.objects.all():
        print(f'  - {cd.nombre_campo_bd} ({cd.tipo_dato})')