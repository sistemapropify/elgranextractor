#!/usr/bin/env python
"""
Verificar estructura de tablas property_types y users.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connections

conn = connections['propifai']
with conn.cursor() as c:
    # property_types
    try:
        c.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'property_types'")
        cols = [row[0] for row in c.fetchall()]
        print('Columnas de property_types:', cols)
        c.execute("SELECT TOP 5 * FROM property_types")
        rows = c.fetchall()
        print('Datos de property_types:')
        for r in rows:
            print(r)
    except Exception as e:
        print('Error al consultar property_types:', e)
    
    # users
    try:
        c.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users'")
        cols = [row[0] for row in c.fetchall()]
        print('\nColumnas de users:', cols)
        c.execute("SELECT TOP 5 id, username, email FROM users")
        rows = c.fetchall()
        print('Datos de users (id, username, email):')
        for r in rows:
            print(r)
    except Exception as e:
        print('Error al consultar users:', e)
    
    # Verificar algunos property_type_id en properties
    c.execute("SELECT TOP 5 code, property_type_id, created_by_id FROM properties")
    rows = c.fetchall()
    print('\nEjemplos de properties:')
    for r in rows:
        print(f"  Código: {r[0]}, property_type_id: {r[1]}, created_by_id: {r[2]}")