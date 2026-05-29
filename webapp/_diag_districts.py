import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from django.db import connections

with connections['propifai'].cursor() as cursor:
    cursor.execute("SELECT id, name FROM district ORDER BY id")
    rows = cursor.fetchall()
    print("District IDs:")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")
    
    cursor.execute("""
        SELECT d.id, d.name, COUNT(*) as cant
        FROM property p
        JOIN district d ON d.id = p.district_id
        WHERE p.is_visible = 1 AND p.property_status_id = 3
        GROUP BY d.id, d.name
        ORDER BY cant DESC
    """)
    rows = cursor.fetchall()
    print("\nDistrict distribution (available properties):")
    for r in rows:
        print(f"  {r[0]}: {r[1]} ({r[2]})")
    
    cursor.execute("""
        SELECT COUNT(*) FROM property 
        WHERE is_visible = 1 AND property_status_id = 3 AND district_id IS NULL
    """)
    cnt = cursor.fetchone()[0]
    print(f"\nAvailable properties with NULL district: {cnt}")
