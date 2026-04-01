#!/usr/bin/env python
"""
Script para ejecutar el SQL de reparación directamente.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def main():
    print("Ejecutando SQL de reparación...")
    
    # Leer el archivo SQL
    sql_path = os.path.join(os.path.dirname(__file__), 'sql_fix_columns.sql')
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Separar las sentencias (simplificado)
    statements = sql_content.split(';')
    
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        
        # Remover PRINT y comentarios (simplificado)
        if stmt.startswith('PRINT') or stmt.startswith('--'):
            print(f"  {stmt}")
            continue
        
        print(f"  Ejecutando: {stmt[:50]}...")
        try:
            with connection.cursor() as cursor:
                cursor.execute(stmt)
                print(f"    ✓ OK")
        except Exception as e:
            print(f"    ✗ Error: {e}")
    
    # Verificar columnas
    print("\nVerificando columnas...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ingestas_propiedadraw'
            ORDER BY ORDINAL_POSITION
        """)
        columns = cursor.fetchall()
        for col_name, data_type, nullable in columns:
            print(f"  - {col_name} ({data_type}, nullable: {nullable})")
    
    print("\n¡Script completado! Reinicia el servidor Django y prueba el admin.")

if __name__ == '__main__':
    main()