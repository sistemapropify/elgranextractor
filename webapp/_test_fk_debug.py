"""
Script para debuggear el problema de foreign keys.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from django.db import connections

print("=" * 60)
print("TEST 1: Conexion a propifai")
print("=" * 60)

try:
    conn = connections['propifai']
    cursor = conn.cursor()
    
    # Test 1: Query simple sin parametros
    print("\n[TEST 1] Query simple...")
    cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo'")
    count = cursor.fetchone()[0]
    print(f"  OK: {count} tablas encontradas")
    
    # Test 2: Query con ? placeholder
    print("\n[TEST 2] Query con ? placeholder...")
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?",
        ('properties', 'dbo')
    )
    count = cursor.fetchone()[0]
    print(f"  OK: {count}")
    
    # Test 3: Query con %s placeholder
    print("\n[TEST 3] Query con %s placeholder...")
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s AND TABLE_SCHEMA = %s",
        ('properties', 'dbo')
    )
    count = cursor.fetchone()[0]
    print(f"  OK: {count}")
    
    # Test 4: REFERENTIAL_CONSTRAINTS
    print("\n[TEST 4] REFERENTIAL_CONSTRAINTS...")
    try:
        cursor.execute("""
            SELECT TOP 5 * FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
        """)
        rows = cursor.fetchall()
        print(f"  OK: {len(rows)} filas")
        for row in rows[:3]:
            print(f"  Row: {row}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 5: KEY_COLUMN_USAGE
    print("\n[TEST 5] KEY_COLUMN_USAGE para properties...")
    try:
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
            WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?
        """, ('properties', 'dbo'))
        rows = cursor.fetchall()
        print(f"  OK: {len(rows)} filas")
        for row in rows[:5]:
            print(f"  {row[0]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 6: Columnas que terminan en _id
    print("\n[TEST 6] Columnas _id en properties...")
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = ? AND TABLE_SCHEMA = ?
          AND (COLUMN_NAME LIKE '%_id' OR COLUMN_NAME LIKE '%_fk%')
        ORDER BY COLUMN_NAME
    """, ('properties', 'dbo'))
    rows = cursor.fetchall()
    print(f"  OK: {len(rows)} columnas FK-like")
    for row in rows:
        print(f"  {row[0]} ({row[1]})")
    
except Exception as e:
    import traceback
    print(f"ERROR GENERAL: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("FIN")
