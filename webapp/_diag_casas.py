import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from django.db import connections

with connections['propifai'].cursor() as cursor:
    # Casa IDs in DB
    cursor.execute("""
        SELECT pt.id, pt.name, COUNT(*) as cnt
        FROM property p
        JOIN property_type pt ON pt.id = p.property_type_id
        WHERE p.is_visible = 1 AND p.property_status_id = 3
        GROUP BY pt.id, pt.name
        ORDER BY cnt DESC
    """)
    rows = cursor.fetchall()
    print("Available properties by type:")
    for r in rows:
        print(f"  type_id={r[0]}: {r[1]} ({r[2]})")
    
    # Check tipo_propiedad 'casa' -> id=1 in property_type table
    cursor.execute("SELECT id, name FROM property_type WHERE is_active = 1")
    print("\nProperty types:")
    for r in cursor.fetchall():
        print(f"  id={r[0]}: {r[1]}")
    
    # See a casa property
    cursor.execute("""
        SELECT id, property_type_id, district_id, price, currency_id, operation_type_id
        FROM property 
        WHERE is_visible = 1 AND property_status_id = 3 AND property_type_id = 1
        LIMIT 3
    """)
    rows = cursor.fetchall()
    print(f"\nSample casa properties:")
    for r in rows:
        print(f"  id={r[0]}, type_id={r[1]}, district={r[2]}, price={r[3]}, currency={r[4]}, op_type={r[5]}")

    # How many casas in distritos Cayma (3) o Cerro Colorado (4)?
    cursor.execute("""
        SELECT COUNT(*) FROM property
        WHERE is_visible = 1 AND property_status_id = 3 
        AND property_type_id = 1
        AND district_id IN (3, 4)
    """)
    cnt = cursor.fetchone()[0]
    print(f"\nCasas disponibles en Cayma o Cerro Colorado: {cnt}")
    
    cursor.execute("""
        SELECT id, district_id, price, currency_id, operation_type_id
        FROM property
        WHERE is_visible = 1 AND property_status_id = 3 
        AND property_type_id = 1
        AND district_id IN (3, 4)
    """)
    rows = cursor.fetchall()
    print(f"Details:")
    for r in rows:
        print(f"  id={r[0]}, district={r[2]}, price={r[2]}, currency={r[3]}, op_type={r[4]}")
