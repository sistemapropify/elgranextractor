import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from django.db import connections

try:
    with connections['propifai'].cursor() as cursor:
        cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME")
        for t in cursor.fetchall():
            print(f"{t[0]}.{t[1]}")
except Exception as e:
    print(f"Error: {e}")
