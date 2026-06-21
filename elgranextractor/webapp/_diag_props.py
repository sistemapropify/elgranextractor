import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from django.db import connections
from collections import Counter

with connections['propifai'].cursor() as cursor:
    cursor.execute("""
        SELECT p.property_type_id, pt.name, COUNT(*) as cnt
        FROM property p
        LEFT JOIN property_type pt ON pt.id = p.property_type_id
        WHERE p.is_visible = 1
        GROUP BY p.property_type_id, pt.name
        ORDER BY cnt DESC
    """)
    rows = cursor.fetchall()
    print("property_type_id distribution (visible properties):")
    for r in rows:
        print(f"  {r[0]}: {r[1]} ({r[2]})")
    
    cursor.execute("""
        SELECT p.property_status_id, ps.name, COUNT(*) as cnt
        FROM property p
        LEFT JOIN property_status ps ON ps.id = p.property_status_id
        WHERE p.is_visible = 1
        GROUP BY p.property_status_id, ps.name
        ORDER BY cnt DESC
    """)
    rows = cursor.fetchall()
    print("\nproperty_status_id distribution:")
    for r in rows:
        print(f"  {r[0]}: {r[1]} ({r[2]})")
    
    cursor.execute("""
        SELECT availability_status, COUNT(*) as cnt
        FROM property
        WHERE is_visible = 1
        GROUP BY availability_status
        ORDER BY cnt DESC
    """)
    rows = cursor.fetchall()
    print("\navailability_status distribution:")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")
    
    cursor.execute("SELECT COUNT(*) FROM property WHERE is_visible = 1 AND property_type_id IS NULL")
    cnt = cursor.fetchone()[0]
    print(f"\nVisible with NULL property_type_id: {cnt}")
