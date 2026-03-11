#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import CampoDinamico, PropiedadRaw

print('=== Campos Dinámicos ===')
print(f'Total: {CampoDinamico.objects.count()}')
for cd in CampoDinamico.objects.all():
    print(f'  - {cd.nombre_campo_bd} ({cd.tipo_dato}) - {cd.titulo_display}')

print('\n=== Atributos Extras (muestra de keys únicas) ===')
# Obtener algunas propiedades
props = PropiedadRaw.objects.all()[:10]
keys_set = set()
for p in props:
    if p.atributos_extras:
        keys_set.update(p.atributos_extras.keys())
print(f'Keys encontradas en primeros 10 registros: {sorted(keys_set)}')

# Contar total de keys únicas en toda la tabla
all_keys = set()
for p in PropiedadRaw.objects.only('atributos_extras').iterator():
    if p.atributos_extras:
        all_keys.update(p.atributos_extras.keys())
print(f'Total keys únicas en toda la tabla: {len(all_keys)}')
print('Primeras 20 keys:', sorted(list(all_keys))[:20])