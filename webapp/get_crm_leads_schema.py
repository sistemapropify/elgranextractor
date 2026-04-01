#!/usr/bin/env python
"""
Script para obtener el esquema de la tabla crm_leads.
"""
import os
import sys
import django
from django.db import connections

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def get_crm_leads_schema():
    print("OBTENIENDO ESQUEMA DE CRM_LEADS")
    print("=" * 60)
    
    connection = connections['propifai']
    
    try:
        with connection.cursor() as cursor:
            # Obtener columnas de la tabla crm_leads
            cursor.execute("""
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    CHARACTER_MAXIMUM_LENGTH,
                    NUMERIC_PRECISION,
                    NUMERIC_SCALE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'crm_leads'
                ORDER BY ORDINAL_POSITION
            """)
            
            columns = cursor.fetchall()
            
            print(f"Total de columnas: {len(columns)}")
            print("\nColumnas:")
            print("-" * 80)
            for col in columns:
                col_name, data_type, nullable, char_max_len, num_precision, num_scale = col
                nullable_str = 'NULL' if nullable == 'YES' else 'NOT NULL'
                extra = ''
                if char_max_len:
                    extra = f" ({char_max_len})"
                elif num_precision is not None:
                    if num_scale is not None and num_scale > 0:
                        extra = f" ({num_precision},{num_scale})"
                    else:
                        extra = f" ({num_precision})"
                print(f"{col_name}: {data_type}{extra} {nullable_str}")
            
            # Obtener algunas filas de ejemplo para ver valores
            print("\n\nPrimeras 5 filas de ejemplo:")
            print("-" * 80)
            cursor.execute("SELECT TOP 5 * FROM dbo.crm_leads")
            rows = cursor.fetchall()
            if rows:
                # Obtener nombres de columnas
                cursor.execute("""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'crm_leads'
                    ORDER BY ORDINAL_POSITION
                """)
                col_names = [row[0] for row in cursor.fetchall()]
                print("Columnas:", col_names)
                for i, row in enumerate(rows):
                    print(f"\nFila {i+1}:")
                    for j, val in enumerate(row):
                        col_name = col_names[j]
                        # Truncar valores largos
                        val_str = str(val)[:100] + '...' if val and len(str(val)) > 100 else str(val)
                        print(f"  {col_name}: {val_str}")
            else:
                print("No hay filas en la tabla.")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    get_crm_leads_schema()