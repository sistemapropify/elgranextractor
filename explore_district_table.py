#!/usr/bin/env python
"""
Explorar la tabla properties_district y su relación con properties.
"""
import os
import sys
import django

sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connections

def explore_district():
    conn = connections['propifai']
    with conn.cursor() as cursor:
        # Verificar si existe la tabla
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'properties_district'")
        if not cursor.fetchone():
            print("Tabla properties_district no existe")
            return
        
        # Obtener columnas
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'properties_district'")
        columns = [row[0] for row in cursor.fetchall()]
        print(f"Columnas de properties_district: {columns}")
        
        # Verificar datos de ejemplo
        cursor.execute("SELECT TOP 5 * FROM properties_district")
        rows = cursor.fetchall()
        print("\nPrimeras 5 filas de properties_district:")
        for row in rows:
            print(row)
        
        # Verificar relación con properties
        cursor.execute("SELECT TOP 5 id, district FROM properties")
        props = cursor.fetchall()
        print("\nPrimeras 5 propiedades (id, district):")
        for prop in props:
            print(prop)
            # Obtener nombre del distrito si district es un número
            if prop[1]:
                cursor.execute("SELECT name FROM properties_district WHERE id = %s", [prop[1]])
                district_name = cursor.fetchone()
                print(f"  -> Nombre distrito: {district_name}")

if __name__ == '__main__':
    explore_district()