#!/usr/bin/env python
"""
Script para verificar tablas en la base de datos propifai.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from django.db import connections

def check_propifai_tables():
    """Verifica las tablas en la base de datos propifai."""
    print("=== Verificando tablas en base de datos propifai ===\n")
    
    try:
        # Verificar conexión
        conn = connections['propifai']
        cursor = conn.cursor()
        
        # Verificar si la conexión funciona
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        print(f"[OK] Conexión exitosa a 'propifai': {result}")
        
        # Listar todas las tablas
        cursor.execute("""
            SELECT 
                TABLE_SCHEMA,
                TABLE_NAME,
                TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        
        tables = cursor.fetchall()
        print(f"\nTotal de tablas encontradas: {len(tables)}\n")
        
        # Mostrar tablas
        for i, (schema, table, table_type) in enumerate(tables, 1):
            print(f"{i:3}. {schema}.{table} ({table_type})")
            
            # Contar filas para esta tabla
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{schema}].[{table}]")
                count = cursor.fetchone()[0]
                print(f"     → {count:,} filas")
            except Exception as e:
                print(f"     → Error contando filas: {e}")
        
        # Buscar específicamente tablas relacionadas con propiedades
        print("\n=== Buscando tablas relacionadas con propiedades ===\n")
        property_tables = []
        for schema, table, table_type in tables:
            table_lower = table.lower()
            if any(keyword in table_lower for keyword in ['prop', 'inmueble', 'casa', 'departamento', 'terreno']):
                property_tables.append((schema, table, table_type))
        
        if property_tables:
            print(f"Encontradas {len(property_tables)} tablas relacionadas con propiedades:\n")
            for schema, table, table_type in property_tables:
                print(f"  - {schema}.{table}")
                
                # Mostrar algunas columnas
                try:
                    cursor.execute(f"""
                        SELECT TOP 5 COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
                        ORDER BY ORDINAL_POSITION
                    """)
                    columns = cursor.fetchall()
                    print(f"    Columnas: {', '.join([col[0] for col in columns[:5]])}")
                    if len(columns) > 5:
                        print(f"    ... y {len(columns) - 5} más")
                except Exception as e:
                    print(f"    Error obteniendo columnas: {e}")
        else:
            print("No se encontraron tablas relacionadas con propiedades.")
            
        # Verificar si existe la tabla 'properties'
        print("\n=== Verificando tabla 'properties' específicamente ===\n")
        found = False
        for schema, table, table_type in tables:
            if table.lower() == 'properties':
                found = True
                print(f"[OK] Tabla 'properties' encontrada en esquema '{schema}'")
                
                # Mostrar estructura
                cursor.execute(f"""
                    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
                    ORDER BY ORDINAL_POSITION
                """)
                columns = cursor.fetchall()
                print(f"  Estructura ({len(columns)} columnas):")
                for col_name, data_type, max_len, nullable in columns[:10]:
                    type_info = f"{data_type}"
                    if max_len:
                        type_info += f"({max_len})"
                    print(f"    - {col_name}: {type_info} {'NULL' if nullable == 'YES' else 'NOT NULL'}")
                if len(columns) > 10:
                    print(f"    ... y {len(columns) - 10} columnas más")
                break
        
        if not found:
            print("[ERROR] Tabla 'properties' NO encontrada en ninguna base de datos.")
            print("\nTablas disponibles que podrían ser relevantes:")
            for schema, table, table_type in tables:
                print(f"  - {schema}.{table}")
        
        cursor.close()
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_propifai_tables()