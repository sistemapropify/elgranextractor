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

# 1. Verificar columnas de la tabla
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'propifai_propifaiproperty'
        ORDER BY COLUMN_NAME
    """)
    print("Columnas de propifai_propifaiproperty:")
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]})")

# 2. Buscar columnas que contengan 'type' o 'tipo'
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'propifai_propifaiproperty' 
        AND (COLUMN_NAME LIKE '%type%' OR COLUMN_NAME LIKE '%tipo%')
    """)
    print("\nColumnas relacionadas con tipo:")
    for row in cursor.fetchall():
        print(f"  {row[0]}")

# 3. Ver valores de property_type_id
with connection.cursor() as cursor:
    cursor.execute("SELECT DISTINCT property_type_id FROM propifai_propifaiproperty WHERE property_type_id IS NOT NULL")
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
from propifai.models import PropifaiProperty
import inspect
for field in PropifaiProperty._meta.fields:
    if 'type' in field.name or 'tipo' in field.name:
        print(f"\nCampo en modelo: {field.name} ({field.__class__.__name__})")
        if hasattr(field, 'related_model'):
            print(f"  Relacionado con: {field.related_model}")