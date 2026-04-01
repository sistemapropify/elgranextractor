#!/usr/bin/env python
"""
Script para obtener datos reales de las tablas property_type y users.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connections

# Usar la conexión 'propifai' (según settings)
conn = connections['propifai']
with conn.cursor() as cursor:
    # 1. Verificar si existe la tabla property_type
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'property_type'")
    if cursor.fetchone():
        print("Tabla property_type encontrada.")
        # Obtener columnas
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'property_type'")
        cols = [row[0] for row in cursor.fetchall()]
        print(f"Columnas: {cols}")
        # Obtener datos
        cursor.execute("SELECT TOP 10 * FROM property_type")
        rows = cursor.fetchall()
        print("Primeras 10 filas:")
        for r in rows:
            print(f"  {r}")
    else:
        print("Tabla property_type NO encontrada.")
    
    # 2. Verificar tabla users
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'users'")
    if cursor.fetchone():
        print("\nTabla users encontrada.")
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users'")
        cols = [row[0] for row in cursor.fetchall()]
        print(f"Columnas: {cols}")
        cursor.execute("SELECT TOP 10 * FROM users")
        rows = cursor.fetchall()
        print("Primeras 10 filas:")
        for r in rows:
            print(f"  {r}")
    else:
        print("\nTabla users NO encontrada.")
    
    # 3. Verificar si la tabla properties tiene columnas property_type_id y created_by
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'properties'")
    all_cols = [row[0] for row in cursor.fetchall()]
    print(f"\nColumnas de la tabla properties:")
    for col in all_cols:
        print(f"  {col}")
    
    # 4. Hacer un JOIN para ver datos reales
    if 'property_type_id' in all_cols:
        print("\nRealizando JOIN entre properties y property_type:")
        cursor.execute("""
            SELECT TOP 5 p.code, p.title, pt.name as property_type_name
            FROM properties p
            LEFT JOIN property_type pt ON p.property_type_id = pt.id
        """)
        rows = cursor.fetchall()
        for r in rows:
            print(f"  Código: {r[0]}, Título: {r[1]}, Tipo: {r[2]}")
    
    if 'created_by' in all_cols:
        print("\nRealizando JOIN entre properties y users:")
        cursor.execute("""
            SELECT TOP 5 p.code, u.username, u.email
            FROM properties p
            LEFT JOIN users u ON p.created_by = u.id
        """)
        rows = cursor.fetchall()
        for r in rows:
            print(f"  Código: {r[0]}, Usuario: {r[1]}, Email: {r[2]}")