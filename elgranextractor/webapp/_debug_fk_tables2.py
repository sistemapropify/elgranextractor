"""
Script para debuggear columnas de la tabla 'properties' en BD propifai
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from django.db import connections
from intelligence.services.schema_discovery import SchemaDiscoveryService

output = []

# 1. Columnas de 'properties' en BD propifai
output.append("=== COLUMNAS DE 'properties' (BD propifai) ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'properties' 
            ORDER BY ORDINAL_POSITION
        """)
        cols = cursor.fetchall()
        for c in cols:
            output.append(f"  - {c[0]} ({c[1]})")
except Exception as e:
    output.append(f"ERROR: {e}")

# 2. Columnas que terminan en _id
output.append("\n=== COLUMNAS QUE TERMINAN EN '_id' EN 'properties' ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'properties' 
              AND COLUMN_NAME LIKE '%_id'
            ORDER BY ORDINAL_POSITION
        """)
        cols = cursor.fetchall()
        for c in cols:
            output.append(f"  - {c[0]} ({c[1]})")
        if not cols:
            output.append("  (ninguna)")
except Exception as e:
    output.append(f"ERROR: {e}")

# 3. Probar detect_foreign_keys con 'properties'
output.append("\n=== DETECT FOREIGN KEYS para 'properties' ===")
try:
    fks = SchemaDiscoveryService.detect_foreign_keys('properties', 'dbo', 'propifai')
    output.append(json.dumps(fks, indent=2, default=str))
except Exception as e:
    import traceback
    output.append(f"ERROR: {e}")
    output.append(traceback.format_exc())

# 4. Columnas de garage_types
output.append("\n=== COLUMNAS DE 'garage_types' ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'garage_types' 
            ORDER BY ORDINAL_POSITION
        """)
        cols = cursor.fetchall()
        for c in cols:
            output.append(f"  - {c[0]} ({c[1]})")
except Exception as e:
    output.append(f"ERROR: {e}")

output_path = os.path.join(os.path.dirname(__file__), '_debug_fk_output2.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"Output escrito a {output_path}")
