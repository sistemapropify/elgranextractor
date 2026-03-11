import pandas as pd
df = pd.read_excel('requerimientos/data/inmobiliaria-remax-10-febrero-2026.xlsx')
cols = df.columns.tolist()
print('Columnas del Excel (27):')
for c in cols:
    print(f'  - {c}')

# Mapeo usado en importar_excel_propiedadraw.py
mapeo_manual = {
    'Tipo de Propiedad': 'tipo_propiedad',
    'URL de la Propiedad': 'url_propiedad',
    'Precio (USD)': 'precio_usd',
    'Departamento': 'departamento',
    'Provincia': 'provincia',
    'Distrito': 'distrito',
    'coordenadas': 'coordenadas',
    'Área de Terreno (m²)': 'area_terreno',
    'Área Construida (m²)': 'area_construida',
    'Número de Pisos': 'numero_pisos',
    'Número de Habitaciones': 'numero_habitaciones',
    'Número de Baños': 'numero_banos',
    'Número de Cocheras': 'numero_cocheras',
    'Agente Inmobiliario': 'agente_inmobiliario',
    'Imágenes de la Propiedad': 'imagenes_propiedad',
    'ID de la Propiedad': 'id_propiedad',
    'Fecha de Publicación': 'fecha_publicacion',
    'Descripción Detallada': 'descripcion',
    'Antigüedad': 'antiguedad',
    'Servicio de Agua': 'servicio_agua',
    'Energía Eléctrica': 'energia_electrica',
    'Servicio de Drenaje': 'servicio_drenaje',
    'Servicio de Gas': 'servicio_gas',
    'Email del Agente': 'email_agente',
    'Teléfono del Agente': 'telefono_agente',
    'Oficina RE/MAX': 'oficina_remax',
    'portal': 'portal'
}

print('\nMapeo a campos del modelo:')
for col in cols:
    campo = mapeo_manual.get(col, '???')
    print(f'  {col} -> {campo}')

# Verificar que todos los campos existan en el modelo
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()
from ingestas.models import PropiedadRaw
campos_modelo = [f.name for f in PropiedadRaw._meta.get_fields()]
print('\nCampos en el modelo PropiedadRaw:')
for campo in campos_modelo:
    print(f'  - {campo}')

# Verificar que cada campo mapeado exista
print('\nVerificación de existencia:')
for col, campo in mapeo_manual.items():
    if campo in campos_modelo:
        print(f'  ✓ {campo} existe')
    else:
        print(f'  ✗ {campo} NO existe en el modelo')