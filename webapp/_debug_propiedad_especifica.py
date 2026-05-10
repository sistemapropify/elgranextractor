# -*- coding: utf-8 -*-
"""
DEBUG: Buscar propiedad LG835530090 en dbo.properties y ver sus campos de publicidad
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from django.db import connection

print("=" * 80)
print("BUSCANDO PROPIEDAD LG835530090 EN dbo.properties")
print("=" * 80)

with connection.cursor() as cursor:
    # First, get all columns
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'properties'
        ORDER BY ORDINAL_POSITION
    """)
    all_columns = [row[0] for row in cursor.fetchall()]
    print(f"Total columnas en dbo.properties: {len(all_columns)}")
    
    # Search for the property
    cursor.execute("""
        SELECT * FROM [dbo].[properties] 
        WHERE codigo_unico_propiedad = 'LG835530090'
    """)
    row = cursor.fetchone()
    
    if row:
        print("\nPROPIEDAD ENCONTRADA!")
        print("-" * 80)
        for i, col in enumerate(all_columns):
            val = row[i]
            if val is not None:
                val_str = str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                print(f"  {col}: {val_str}")
            else:
                print(f"  {col}: NULL")
    else:
        print("\nNO se encontro la propiedad con codigo_unico_propiedad = 'LG835530090'")
        
        # Try searching with different approaches
        cursor.execute("""
            SELECT codigo_unico_propiedad, title, real_address, price 
            FROM [dbo].[properties] 
            WHERE codigo_unico_propiedad LIKE '%LG8355%'
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"\nPropiedades con codigo similar:")
            for r in rows:
                print(f"  {r}")
        else:
            cursor.execute("""
                SELECT codigo_unico_propiedad, title, real_address, price 
                FROM [dbo].[properties] 
                WHERE real_address LIKE '%Emperatriz%'
            """)
            rows = cursor.fetchall()
            if rows:
                print(f"\nPropiedades con direccion similar:")
                for r in rows:
                    print(f"  {r}")
            else:
                cursor.execute("""
                    SELECT codigo_unico_propiedad, title, real_address, price 
                    FROM [dbo].[properties] 
                    WHERE title LIKE '%Emperatriz%'
                """)
                rows = cursor.fetchall()
                if rows:
                    print(f"\nPropiedades con titulo similar:")
                    for r in rows:
                        print(f"  {r}")
                else:
                    # List first 10 properties to see what's there
                    cursor.execute("""
                        SELECT TOP 10 codigo_unico_propiedad, title, real_address, price 
                        FROM [dbo].[properties] 
                        ORDER BY id
                    """)
                    rows = cursor.fetchall()
                    print(f"\nPrimeras 10 propiedades en la tabla:")
                    for r in rows:
                        print(f"  {r}")
                    
                    # Count total
                    cursor.execute("SELECT COUNT(*) FROM [dbo].[properties]")
                    total = cursor.fetchone()[0]
                    print(f"\nTotal propiedades en tabla: {total}")

print("\n" + "=" * 80)
print("VERIFICANDO CAMPOS amenities EN ALGUNAS PROPIEDADES")
print("=" * 80)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT TOP 5 codigo_unico_propiedad, title, amenities, description
        FROM [dbo].[properties] 
        WHERE amenities IS NOT NULL AND amenities != ''
        ORDER BY id
    """)
    rows = cursor.fetchall()
    if rows:
        print(f"\nPropiedades con amenities NO vacio ({len(rows)}):")
        for r in rows:
            print(f"  {r[0]} - {r[1]}")
            print(f"    amenities: {r[2]}")
            print(f"    description: {str(r[3])[:200] if r[3] else 'NULL'}")
    else:
        print("\nNINGUNA propiedad tiene amenities con datos!")
        
        # Check how many have non-null amenities
        cursor.execute("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN amenities IS NULL THEN 1 ELSE 0 END),
                   SUM(CASE WHEN amenities = '' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN amenities IS NOT NULL AND amenities != '' THEN 1 ELSE 0 END)
            FROM [dbo].[properties]
        """)
        stats = cursor.fetchone()
        print(f"\nEstadisticas de amenities:")
        print(f"  Total propiedades: {stats[0]}")
        print(f"  amenities IS NULL: {stats[1]}")
        print(f"  amenities = '': {stats[2]}")
        print(f"  amenities con datos: {stats[3]}")

print("\n" + "=" * 80)
print("BUSCANDO CAMPOS DE PUBLICIDAD EN LA APP PROJIFAI")
print("=" * 80)

# Check if there's a propifai model with advertising fields
try:
    from propifai.models import Property
    print(f"\nModelo Property encontrado en propifai.models")
    for field in Property._meta.get_fields():
        print(f"  Campo: {field.name} ({type(field).__name__})")
except Exception as e:
    print(f"\nNo se pudo importar Property de propifai: {e}")

# Check for any model with publicidad-related fields
try:
    from django.apps import apps
    for model in apps.get_models():
        model_name = model.__name__
        for field in model._meta.get_fields():
            fname = field.name.lower()
            if any(kw in fname for kw in ['publicidad', 'anuncio', 'advertising', 'coworking', 'terraza', 'alcabala', 'amenitie', 'comodidad', 'servicio', 'incluye', 'beneficio', 'caracteristica']):
                print(f"\nCampo de publicidad encontrado: {model_name}.{field.name}")
except Exception as e:
    print(f"Error buscando modelos: {e}")

print("\n" + "=" * 80)
print("DIAGNOSTICO COMPLETADO")
print("=" * 80)
