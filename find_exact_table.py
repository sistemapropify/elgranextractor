#!/usr/bin/env python
"""
Encontrar la tabla exacta de property_type.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connections

conn = connections['propifai']
with conn.cursor() as cursor:
    # Buscar cualquier tabla que tenga 'property_type' en el nombre (case insensitive)
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%property_type%'")
    rows = cursor.fetchall()
    print("Tablas que contienen 'property_type':")
    for r in rows:
        print(f"  {r[0]}")
        # Mostrar columnas
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{r[0]}'")
        cols = [row[0] for row in cursor.fetchall()]
        print(f"    Columnas: {cols}")
        # Mostrar algunos datos
        cursor.execute(f"SELECT TOP 3 * FROM [{r[0]}]")
        data = cursor.fetchall()
        for d in data:
            print(f"      {d}")
    
    # Si no hay ninguna, buscar tablas que tengan columna 'name' y sean probablemente de tipos
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE COLUMN_NAME = 'name' 
        GROUP BY TABLE_NAME 
        HAVING COUNT(*) >= 1
    """)
    tables_with_name = [row[0] for row in cursor.fetchall()]
    print("\nTablas que tienen columna 'name':")
    for t in tables_with_name:
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{t}'")
        cols = [row[0] for row in cursor.fetchall()]
        if 'id' in cols:
            print(f"  {t}: {cols}")
            # Ver si tiene datos que parezcan tipos de propiedad
            cursor.execute(f"SELECT TOP 3 id, name FROM [{t}]")
            rows = cursor.fetchall()
            for r in rows:
                print(f"    {r[0]}: {r[1]}")
    
    # También podemos intentar hacer un JOIN con properties usando property_type_id y ver qué tabla funciona
    print("\nIntentando JOIN con posibles tablas...")
    cursor.execute("SELECT DISTINCT property_type_id FROM properties WHERE property_type_id IS NOT NULL")
    ids = [row[0] for row in cursor.fetchall()]
    for tid in ids[:5]:
        print(f"  Para property_type_id = {tid}:")
        for t in tables_with_name:
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{t}'")
            cols = [row[0] for row in cursor.fetchall()]
            if 'id' in cols:
                try:
                    cursor.execute(f"SELECT name FROM [{t}] WHERE id = {tid}")
                    row = cursor.fetchone()
                    if row:
                        print(f"    Encontrado en tabla {t}: {row[0]}")
                        break
                except:
                    pass