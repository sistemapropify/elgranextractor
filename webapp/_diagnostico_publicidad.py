# -*- coding: utf-8 -*-
"""
DIAGNOSTICO: Donde estan los datos de publicidad de las propiedades?
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from django.db import connections

conn = connections['propifai']

print("=" * 80)
print("1. BUSCAR PROPIEDAD LG835530090")
print("=" * 80)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'properties'
        ORDER BY ORDINAL_POSITION
    """)
    all_columns = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM [dbo].[properties] WHERE codigo_unico_propiedad = 'LG835530090'")
    row = cursor.fetchone()
    
    if row:
        print("PROPIEDAD ENCONTRADA:")
        for i, col in enumerate(all_columns):
            val = row[i]
            if val is not None:
                val_str = str(val)
                if len(val_str) > 500:
                    val_str = val_str[:500] + "..."
                print(f"  {col}: {val_str}")
            else:
                print(f"  {col}: NULL")
    else:
        print("NO encontrada. Buscando en otras tablas...")
        cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        for tbl in [r[0] for r in cursor.fetchall()]:
            try:
                cursor.execute("SELECT COUNT(*) FROM [{}] WHERE codigo_unico_propiedad = 'LG835530090'".format(tbl))
                if cursor.fetchone()[0] > 0:
                    print(f"ENCONTRADA en tabla: {tbl}")
                    cursor.execute("SELECT * FROM [{}] WHERE codigo_unico_propiedad = 'LG835530090'".format(tbl))
                    cols2 = [desc[0] for desc in cursor.description]
                    row2 = cursor.fetchone()
                    for i, c in enumerate(cols2):
                        print(f"  {c}: {row2[i]}")
            except:
                pass

print("\n" + "=" * 80)
print("2. VERIFICAR amenities EN TODAS LAS PROPIEDADES")
print("=" * 80)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN amenities IS NULL OR amenities = '' THEN 0 ELSE 1 END) as con_datos,
            SUM(CASE WHEN amenities IS NULL THEN 1 ELSE 0 END) as es_null,
            SUM(CASE WHEN amenities = '' THEN 1 ELSE 0 END) as es_vacio
        FROM [dbo].[properties]
    """)
    stats = cursor.fetchone()
    print(f"  Con datos: {stats[0]}")
    print(f"  NULL: {stats[1]}")
    print(f"  Vacio: {stats[2]}")

print("\n" + "=" * 80)
print("3. BUSCAR TABLAS CON POSIBLES DATOS DE PUBLICIDAD")
print("=" * 80)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE (TABLE_NAME LIKE '%prop%' OR TABLE_NAME LIKE '%property%')
           AND (LOWER(COLUMN_NAME) LIKE '%descrip%' 
             OR LOWER(COLUMN_NAME) LIKE '%detalle%'
             OR LOWER(COLUMN_NAME) LIKE '%observac%'
             OR LOWER(COLUMN_NAME) LIKE '%nota%'
             OR LOWER(COLUMN_NAME) LIKE '%coment%'
             OR LOWER(COLUMN_NAME) LIKE '%extras%'
             OR LOWER(COLUMN_NAME) LIKE '%atributo%'
             OR LOWER(COLUMN_NAME) LIKE '%caracteris%'
             OR LOWER(COLUMN_NAME) LIKE '%incluye%'
             OR LOWER(COLUMN_NAME) LIKE '%beneficio%'
             OR LOWER(COLUMN_NAME) LIKE '%servicio%'
             OR LOWER(COLUMN_NAME) LIKE '%comodidad%')
        ORDER BY TABLE_NAME
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"Campos encontrados ({len(rows)}):")
        for r in rows:
            print(f"  {r[0]}.{r[1]}")
    else:
        print("No se encontraron campos adicionales")

print("\n" + "=" * 80)
print("4. VER TABLAS RELACIONADAS A PROPERTIES (FKs)")
print("=" * 80)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT 
            fk.name AS FK_name,
            OBJECT_NAME(fk.parent_object_id) AS source_table,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS source_column,
            OBJECT_NAME(fk.referenced_object_id) AS target_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS target_column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE OBJECT_NAME(fk.parent_object_id) = 'properties'
           OR OBJECT_NAME(fk.referenced_object_id) = 'properties'
    """)
    fks = cursor.fetchall()
    if fks:
        print("Foreign Keys de properties:")
        for fk in fks:
            print(f"  {fk[0]}: {fk[1]}.{fk[2]} -> {fk[3]}.{fk[4]}")
    else:
        print("No hay FKs definidas en properties")

print("\n" + "=" * 80)
print("5. BUSCAR TABLA property_images O SIMILAR")
print("=" * 80)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
          AND TABLE_NAME LIKE '%image%' OR TABLE_NAME LIKE '%photo%' OR TABLE_NAME LIKE '%imagen%'
          OR TABLE_NAME LIKE '%picture%' OR TABLE_NAME LIKE '%media%'
          OR TABLE_NAME LIKE '%document%' OR TABLE_NAME LIKE '%archivo%'
          OR TABLE_NAME LIKE '%publicidad%' OR TABLE_NAME LIKE '%anuncio%'
    """)
    rows = cursor.fetchall()
    if rows:
        print("Tablas encontradas:")
        for r in rows:
            print(f"  {r[0]}")
            cursor.execute("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s
            """, [r[0]])
            for c in cursor.fetchall():
                print(f"    - {c[0]}")
    else:
        print("No se encontraron tablas adicionales")

print("\nDIAGNOSTICO COMPLETADO")
