import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from django.db import connection
from ingestas.models import PropiedadRaw

# Obtener columnas de la BD
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
        ORDER BY ORDINAL_POSITION
    """)
    db_columns = [row[0] for row in cursor.fetchall()]

print("Columnas en BD:", db_columns)
print("\nCampos del modelo:")
for field in PropiedadRaw._meta.fields:
    db_column = field.db_column if field.db_column else field.column
    print(f"  {field.name} -> {db_column} (tipo: {field.get_internal_type()})")

# Verificar coincidencias
for field in PropiedadRaw._meta.fields:
    db_column = field.db_column if field.db_column else field.column
    if db_column not in db_columns:
        print(f"ADVERTENCIA: {field.name} mapea a columna '{db_column}' que no existe en BD")
    else:
        print(f"OK: {field.name} -> {db_column}")