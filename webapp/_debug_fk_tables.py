"""
Script para debuggear la detección de FK en propifai_propiedad.
Escribe resultados a un archivo para poder verlos.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from django.db import connections
from intelligence.services.schema_discovery import SchemaDiscoveryService

output = []

# 1. Ver conexiones disponibles
output.append("=== CONEXIONES DISPONIBLES ===")
output.append(str(list(connections.databases.keys())))

# 2. Intentar listar tablas de propifai
output.append("\n=== TABLAS EN propifai (dbo) ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo' ORDER BY TABLE_NAME")
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            output.append(f"  - {t}")
except Exception as e:
    output.append(f"ERROR: {e}")

# 3. Ver columnas de propifai_propiedad
output.append("\n=== COLUMNAS DE propifai_propiedad ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'propifai_propiedad' ORDER BY ORDINAL_POSITION")
        cols = cursor.fetchall()
        for c in cols:
            output.append(f"  - {c[0]} ({c[1]})")
except Exception as e:
    output.append(f"ERROR: {e}")

# 4. Probar SchemaDiscoveryService.detect_foreign_keys directamente
output.append("\n=== DETECT FOREIGN KEYS ===")
try:
    fks = SchemaDiscoveryService.detect_foreign_keys('propifai_propiedad', 'dbo', 'propifai')
    output.append(json.dumps(fks, indent=2, default=str))
except Exception as e:
    import traceback
    output.append(f"ERROR: {e}")
    output.append(traceback.format_exc())

# 5. Probar _guess_referenced_table para garage_type
output.append("\n=== _guess_referenced_table('garage_type') ===")
try:
    conn = connections['propifai']
    result = SchemaDiscoveryService._guess_referenced_table('garage_type', conn, 'dbo')
    output.append(f"Resultado: {result}")
except Exception as e:
    import traceback
    output.append(f"ERROR: {e}")
    output.append(traceback.format_exc())

# 6. Buscar tablas que contengan 'garage' en el nombre
output.append("\n=== TABLAS QUE CONTIENEN 'garage' ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo' AND TABLE_NAME LIKE '%garage%' ORDER BY TABLE_NAME")
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            output.append(f"  - {t}")
        if not tables:
            output.append("  (ninguna)")
except Exception as e:
    output.append(f"ERROR: {e}")

# 7. Buscar tablas que contengan 'tipo' o 'type' en el nombre
output.append("\n=== TABLAS QUE CONTIENEN 'tipo' o 'type' ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo' AND (TABLE_NAME LIKE '%tipo%' OR TABLE_NAME LIKE '%type%') ORDER BY TABLE_NAME")
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            output.append(f"  - {t}")
        if not tables:
            output.append("  (ninguna)")
except Exception as e:
    output.append(f"ERROR: {e}")

# 8. Ver columnas que terminan en _id en propifai_propiedad
output.append("\n=== COLUMNAS QUE TERMINAN EN '_id' EN propifai_propiedad ===")
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'dbo' 
              AND TABLE_NAME = 'propifai_propiedad' 
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

# Escribir resultados
output_path = os.path.join(os.path.dirname(__file__), '_debug_fk_output.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"Output escrito a {output_path}")
