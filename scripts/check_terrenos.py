"""Consulta cuantos terrenos hay en Cerro Colorado en la BD."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django
django.setup()

from django.db import connections

with connections['propifai'].cursor() as cursor:
    # Total terrenos en Cerro Colorado
    cursor.execute("""
        SELECT COUNT(*) FROM vwd_propiedades_propify_listado 
        WHERE district_name = 'Cerro Colorado' 
        AND property_type_name = 'Terreno'
    """)
    total = cursor.fetchone()[0]
    print(f"\n=== TERRENOS EN CERRO COLORADO: {total} ===\n")
    
    # Listar todos
    cursor.execute("""
        SELECT title, price, currency_name, status_name, code 
        FROM vwd_propiedades_propify_listado 
        WHERE district_name = 'Cerro Colorado' 
        AND property_type_name = 'Terreno'
    """)
    for row in cursor.fetchall():
        print(f"  - {row[0]} | {row[1]} {row[2]} | {row[3]} | cod: {row[4]}")
