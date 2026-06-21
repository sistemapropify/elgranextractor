"""
Debug: Revisar tabla properties en propifai y el chat RAG
"""
import os, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from django.db import connections

print("=" * 70)
print("1. TABLA 'properties' EN BD PROPRIFY")
print("=" * 70)
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' AND TABLE_NAME='properties'")
        if cursor.fetchone():
            print("Tabla 'properties' EXISTE en propifai")
            cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='properties'")
            cols = cursor.fetchall()
            print(f"Columnas ({len(cols)}):")
            for c in cols:
                print(f"  - {c[0]} ({c[1]})")
            
            cursor.execute("SELECT COUNT(*) FROM [properties]")
            total = cursor.fetchone()[0]
            print(f"Total registros: {total}")
            
            # Ver currency_id
            if 'currency_id' in [c[0] for c in cols]:
                cursor.execute("SELECT DISTINCT currency_id FROM [properties]")
                currencies = cursor.fetchall()
                print(f"Valores de currency_id: {currencies}")
            
            # Precios
            cursor.execute("SELECT TOP 5 id, title, price, currency_id FROM [properties] WHERE price IS NOT NULL")
            for row in cursor.fetchall():
                print(f"  ID={row[0]}, Title={row[1]}, Price={row[2]}, Currency={row[3]}")
            
            # Cayma
            district_cols = [c[0] for c in cols if 'district' in c[0].lower() or 'distrito' in c[0].lower()]
            for dc in district_cols:
                cursor.execute(f"SELECT COUNT(*) FROM [properties] WHERE LOWER([{dc}]) LIKE '%cayma%'")
                count = cursor.fetchone()[0]
                print(f"Propiedades en Cayma ('{dc}'): {count}")
                if count > 0:
                    cursor.execute(f"SELECT TOP 3 id, title, price, currency_id, [{dc}] FROM [properties] WHERE LOWER([{dc}]) LIKE '%cayma%'")
                    for row in cursor.fetchall():
                        print(f"  ID={row[0]}, Title={row[1]}, Price={row[2]}, Currency={row[3]}, Dist={row[4]}")
            
            # Mirasol
            urb_cols = [c[0] for c in cols if 'urbanization' in c[0].lower() or 'urbanizacion' in c[0].lower()]
            for uc in urb_cols:
                cursor.execute(f"SELECT COUNT(*) FROM [properties] WHERE LOWER([{uc}]) LIKE '%mirasol%'")
                count = cursor.fetchone()[0]
                print(f"Propiedades Mirasol ('{uc}'): {count}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
print("2. TABLA currencies")
print("=" * 70)
try:
    conn = connections['propifai']
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM [currencies]")
        for row in cursor.fetchall():
            print(row)
except Exception as e:
    print(f"Error: {e}")
