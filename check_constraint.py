#!/usr/bin/env python
"""
Script para verificar la restricción CHECK en la tabla intelligence_documents
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connection

def check_constraint():
    """Verificar restricciones CHECK en la tabla intelligence_documents"""
    with connection.cursor() as cursor:
        # Obtener información de restricciones CHECK
        cursor.execute("""
            SELECT 
                tc.CONSTRAINT_NAME,
                tc.CONSTRAINT_TYPE,
                cc.CHECK_CLAUSE
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            LEFT JOIN INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc 
                ON tc.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = 'intelligence_documents'
                AND tc.CONSTRAINT_TYPE = 'CHECK'
        """)
        
        constraints = cursor.fetchall()
        
        print("Restricciones CHECK en tabla intelligence_documents:")
        for constraint_name, constraint_type, check_clause in constraints:
            print(f"  Nombre: {constraint_name}")
            print(f"  Tipo: {constraint_type}")
            print(f"  Cláusula: {check_clause}")
            print()
        
        # También verificar la definición de la columna metadata_json
        cursor.execute("""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'intelligence_documents'
                AND COLUMN_NAME = 'metadata_json'
        """)
        
        column_info = cursor.fetchall()
        
        print("Información de columna metadata_json:")
        for col_name, data_type, is_nullable, max_length in column_info:
            print(f"  Columna: {col_name}")
            print(f"  Tipo: {data_type}")
            print(f"  Nullable: {is_nullable}")
            print(f"  Longitud máxima: {max_length}")
        
        # Verificar si hay datos existentes en la tabla
        cursor.execute("SELECT COUNT(*) FROM intelligence_documents")
        count = cursor.fetchone()[0]
        print(f"\nDocumentos existentes en tabla: {count}")
        
        # Verificar un documento de ejemplo para ver el formato de metadata_json
        if count > 0:
            cursor.execute("SELECT TOP 1 metadata_json FROM intelligence_documents")
            example = cursor.fetchone()
            if example and example[0]:
                print(f"\nEjemplo de metadata_json (primeros 200 chars):")
                print(example[0][:200])
                
                # Intentar parsear JSON
                import json
                try:
                    parsed = json.loads(example[0])
                    print(f"JSON parseado correctamente. Tipo: {type(parsed)}")
                except Exception as e:
                    print(f"Error parseando JSON: {e}")

if __name__ == '__main__':
    print("=== Verificación de restricción CHECK ===")
    check_constraint()