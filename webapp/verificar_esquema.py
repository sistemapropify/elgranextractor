#!/usr/bin/env python
"""
Script para verificar el esquema de la base de datos y el estado de migraciones.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

from django.db.migrations.recorder import MigrationRecorder

def main():
    print("=== Verificación de migraciones ===")
    
    # Obtener migraciones aplicadas
    applied = MigrationRecorder.Migration.objects.filter(app='ingestas').values_list('name', flat=True)
    print(f"Migraciones aplicadas para 'ingestas': {list(applied)}")
    
    # Buscar migraciones relacionadas con condicion y propiedad_verificada
    for mig in applied:
        if 'condicion' in mig or 'propiedad_verificada' in mig:
            print(f"  -> Encontrada migración relevante: {mig}")
    
    print("\n=== Verificación de esquema de tabla PropiedadRaw ===")
    
    # Obtener columnas de la tabla usando SQL directo
    with connection.cursor() as cursor:
        # Para SQL Server
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ingestas_propiedadraw'
            ORDER BY ORDINAL_POSITION
        """)
        columns = cursor.fetchall()
        
        if not columns:
            print("Tabla 'ingestas_propiedadraw' no encontrada.")
            # Intentar con otro nombre (posiblemente sin prefijo)
            cursor.execute("""
                SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME LIKE '%propiedadraw%'
            """)
            tables = cursor.fetchall()
            print(f"Tablas similares encontradas: {tables}")
        else:
            print(f"Columnas encontradas ({len(columns)}):")
            for col in columns:
                print(f"  - {col[0]} ({col[1]}, nullable: {col[2]})")
    
    # Verificar específicamente condicion y propiedad_verificada
    print("\n=== Buscando columnas específicas ===")
    target_cols = ['condicion', 'propiedad_verificada']
    for col in target_cols:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'ingestas_propiedadraw' AND COLUMN_NAME = ?
            """, [col])
            exists = cursor.fetchone()[0]
            print(f"  Columna '{col}': {'EXISTE' if exists else 'NO EXISTE'}")
    
    # Contar registros
    print("\n=== Conteo de registros ===")
    try:
        from ingestas.models import PropiedadRaw
        total = PropiedadRaw.objects.count()
        print(f"Total registros en PropiedadRaw: {total}")
    except Exception as e:
        print(f"Error al contar registros: {e}")

if __name__ == '__main__':
    main()