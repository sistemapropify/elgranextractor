#!/usr/bin/env python
import sys
import os

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.db import connection

print("=== Verificando esquema de tabla ingestas_propiedadraw ===")

# Verificar si la tabla existe
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
    """)
    table_exists = cursor.fetchone()
    if not table_exists:
        print("ERROR: La tabla 'ingestas_propiedadraw' no existe en la base de datos.")
        sys.exit(1)
    else:
        print("✓ Tabla existe.")

# Obtener columnas
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
        ORDER BY ORDINAL_POSITION
    """)
    columns = cursor.fetchall()
    print(f"\nTotal columnas: {len(columns)}")
    print("\nLista de columnas:")
    for col in columns:
        name, dtype, nullable, max_len = col
        extra = f"({max_len})" if max_len else ""
        print(f"  - {name}: {dtype}{extra} {'NULL' if nullable == 'YES' else 'NOT NULL'}")

# Contar registros
with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
    count = cursor.fetchone()[0]
    print(f"\nRegistros en tabla: {count}")

# Verificar algunas columnas nuevas esperadas
expected_new_columns = [
    'portal', 'url_propiedad', 'coordenadas', 'departamento', 'provincia', 
    'distrito', 'area_terreno', 'area_construida', 'numero_pisos', 
    'numero_habitaciones', 'numero_banos', 'numero_cocheras', 
    'agente_inmobiliario', 'imagenes_propiedad', 'id_propiedad', 
    'fecha_publicacion', 'antiguedad', 'servicio_agua', 'energia_electrica', 
    'servicio_drenaje', 'servicio_gas', 'email_agente', 'telefono_agente', 
    'oficina_remax'
]

existing_columns = [col[0].lower() for col in columns]
missing = [col for col in expected_new_columns if col.lower() not in existing_columns]
print(f"\nColumnas nuevas faltantes: {len(missing)}")
if missing:
    for col in missing:
        print(f"  - {col}")