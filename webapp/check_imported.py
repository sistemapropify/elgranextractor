import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db import models

total = PropiedadRaw.objects.count()
print(f'Total registros: {total}')

# Contar por fuente
fuentes = PropiedadRaw.objects.values('fuente_excel').annotate(count=models.Count('id'))
for f in fuentes:
    print(f"Fuente '{f['fuente_excel']}': {f['count']} registros")

# Verificar algunos registros
sample = PropiedadRaw.objects.order_by('id').last()
if sample:
    print('\nÚltimo registro:')
    print(f'  ID: {sample.id}')
    print(f'  Tipo: {sample.tipo_propiedad}')
    print(f'  Precio: {sample.precio_usd}')
    print(f'  Departamento: {sample.departamento}')
    print(f'  URL: {sample.url_propiedad}')
    print(f'  Agente: {sample.agente_inmobiliario}')
    print(f'  Fecha publicación: {sample.fecha_publicacion}')
else:
    print('No hay registros')

# Verificar que no haya campos nulos críticos
print('\nVerificación de nulos:')
campos = ['tipo_propiedad', 'precio_usd', 'departamento', 'url_propiedad']
for campo in campos:
    nulos = PropiedadRaw.objects.filter(**{campo: None}).count()
    print(f'  {campo}: {nulos} nulos')

# Comparar con Excel
import pandas as pd
df = pd.read_excel('requerimientos/data/inmobiliaria-remax-10-febrero-2026.xlsx')
print(f'\nFilas en Excel: {len(df)}')
print(f'Diferencia: {total - len(df)}')