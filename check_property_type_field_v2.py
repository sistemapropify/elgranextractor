#!/usr/bin/env python
"""
Script para verificar el campo property_type_id y su relación.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connection
from propifai.models import PropifaiProperty

# Obtener el nombre de la tabla del modelo
table_name = PropifaiProperty._meta.db_table
print(f"Nombre de tabla del modelo: {table_name}")

# 1. Verificar columnas de la tabla
with connection.cursor() as cursor:
    cursor.execute(f"""
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{table_name}'
        ORDER BY COLUMN_NAME
    """)
    print("\nColumnas de la tabla:")
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]})")

# 2. Buscar columnas que contengan 'type' o 'tipo'
with connection.cursor() as cursor:
    cursor.execute(f"""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{table_name}' 
        AND (COLUMN_NAME LIKE '%type%' OR COLUMN_NAME LIKE '%tipo%')
    """)
    print("\nColumnas relacionadas con tipo:")
    for row in cursor.fetchall():
        print(f"  {row[0]}")

# 3. Ver valores de property_type_id
with connection.cursor() as cursor:
    cursor.execute(f"SELECT DISTINCT property_type_id FROM {table_name} WHERE property_type_id IS NOT NULL")
    distinct_ids = [row[0] for row in cursor.fetchall()]
    print(f"\nValores distintos de property_type_id: {distinct_ids}")
    # Si hay una tabla de referencia, buscar su nombre
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME LIKE '%property_type%' OR TABLE_NAME LIKE '%tipo_propiedad%'
    """)
    ref_tables = [row[0] for row in cursor.fetchall()]
    print(f"Tablas de referencia posibles: {ref_tables}")
    for table in ref_tables:
        cursor.execute(f"SELECT TOP 5 * FROM [{table}]")
        rows = cursor.fetchall()
        print(f"  Contenido de {table}:")
        for r in rows:
            print(f"    {r}")

# 4. Verificar si el modelo Django tiene una relación ForeignKey
print("\nCampos del modelo PropifaiProperty:")
for field in PropifaiProperty._meta.fields:
    if 'type' in field.name or 'tipo' in field.name:
        print(f"  {field.name} ({field.__class__.__name__})")
        if hasattr(field, 'related_model') and field.related_model:
            print(f"    -> Relacionado con: {field.related_model.__name__}")
            # Intentar obtener algunos objetos relacionados
            try:
                related_objects = field.related_model.objects.all()[:5]
                for obj in related_objects:
                    print(f"       - {obj}")
            except Exception as e:
                print(f"       Error al obtener objetos: {e}")

# 5. Probar acceder a property_type desde una instancia
print("\nProbando acceso a property_type desde una instancia:")
prop = PropifaiProperty.objects.first()
if prop:
    print(f"Propiedad ejemplo: {prop.code}")
    # Verificar si tiene atributo property_type
    if hasattr(prop, 'property_type'):
        print(f"  prop.property_type: {prop.property_type}")
    # Verificar si tiene property_type_id
    if hasattr(prop, 'property_type_id'):
        print(f"  prop.property_type_id: {prop.property_type_id}")
    # Intentar acceder a través de relación
    try:
        if prop.property_type_id:
            # Suponiendo que hay un related_name 'property_type'
            related = prop.property_type
            print(f"  prop.property_type (relación): {related}")
    except Exception as e:
        print(f"  Error al acceder a relación: {e}")