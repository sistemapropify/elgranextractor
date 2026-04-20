#!/usr/bin/env python
"""
Script para verificar columnas de la tabla properties
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

def check_columns():
    """Verificar columnas de la tabla properties"""
    
    try:
        # Obtener conexión a la base de datos propifai
        conn = connections['propifai']
        
        with conn.cursor() as cursor:
            # Obtener columnas de la tabla properties
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'properties'
                ORDER BY ORDINAL_POSITION
            """)
            
            columns = cursor.fetchall()
            
            print("Columnas de la tabla 'properties':")
            for col_name, data_type, is_nullable in columns:
                print(f"  {col_name}: {data_type} (Nullable: {is_nullable})")
            
            # También verificar la consulta SQL actual de la colección
            print("\n=== Consulta SQL actual de la colección ===")
            
            from intelligence.models import IntelligenceCollection
            collection = IntelligenceCollection.objects.filter(
                name__icontains='propiedades_propifai',
                is_active=True
            ).first()
            
            if collection:
                print(f"Colección: {collection.name}")
                print(f"SQL: {collection.source_sql}")
                
                # Probar la consulta
                print("\n=== Probando consulta SQL ===")
                try:
                    cursor.execute(collection.source_sql)
                    result_columns = [col[0] for col in cursor.description]
                    print(f"Columnas devueltas: {result_columns}")
                    
                    # Obtener una fila de ejemplo
                    row = cursor.fetchone()
                    if row:
                        print("\nPrimera fila de ejemplo:")
                        for col_name, value in zip(result_columns, row):
                            if value is not None:
                                print(f"  {col_name}: {value} ({type(value).__name__})")
                            else:
                                print(f"  {col_name}: None")
                except Exception as e:
                    print(f"Error ejecutando consulta: {e}")
                    
    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=== Verificación de columnas de tabla ===")
    check_columns()