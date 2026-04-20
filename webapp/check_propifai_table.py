#!/usr/bin/env python
"""
Script para verificar la tabla real de propiedades Propifai.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.apps import apps
from django.db import connection
from propifai.models import PropifaiProperty

def main():
    print("=== Verificación de tabla PropifaiProperty ===")
    
    # 1. Obtener nombre de tabla del modelo
    model_table = PropifaiProperty._meta.db_table
    print(f"1. Modelo PropifaiProperty._meta.db_table: {model_table}")
    
    # 2. Verificar si la tabla existe en la base de datos
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE='BASE TABLE' 
            AND TABLE_NAME = ?
        """, [model_table])
        result = cursor.fetchone()
        
        if result:
            print(f"2. Tabla '{model_table}' EXISTE en la base de datos")
        else:
            print(f"2. Tabla '{model_table}' NO EXISTE en la base de datos")
    
    # 3. Listar todas las tablas relacionadas con propifai
    print("\n3. Tablas relacionadas con 'propifai' en la base de datos:")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE='BASE TABLE' 
            AND TABLE_NAME LIKE '%propifai%'
            ORDER BY TABLE_NAME
        """)
        tables = cursor.fetchall()
        
        for table in tables:
            print(f"   - {table[0]}")
    
    # 4. Verificar si existe tabla 'propifai_propiedad'
    print("\n4. Buscando tabla 'propifai_propiedad':")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE='BASE TABLE' 
            AND TABLE_NAME = 'propifai_propiedad'
        """)
        result = cursor.fetchone()
        
        if result:
            print(f"   Tabla 'propifai_propiedad' EXISTE")
        else:
            print(f"   Tabla 'propifai_propiedad' NO EXISTE")
    
    # 5. Contar registros en la tabla del modelo
    try:
        count = PropifaiProperty.objects.count()
        print(f"\n5. PropifaiProperty.objects.count(): {count} registros")
        
        # Mostrar algunos campos de ejemplo
        if count > 0:
            sample = PropifaiProperty.objects.first()
            print(f"   Ejemplo - ID: {sample.id}, Título: {sample.titulo}")
            print(f"   Campos disponibles: {[f.name for f in PropifaiProperty._meta.fields[:10]]}...")
    except Exception as e:
        print(f"\n5. Error al contar PropifaiProperty: {e}")
    
    # 6. Verificar campos del modelo
    print("\n6. Campos del modelo PropifaiProperty:")
    for field in PropifaiProperty._meta.fields:
        print(f"   - {field.name}: {field.get_internal_type()}")

if __name__ == '__main__':
    main()