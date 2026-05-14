import os, sys, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# Change to webapp directory
sys.path.insert(0, os.path.dirname(__file__))

import django
from django.conf import settings
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Get all migration records
    cursor.execute("SELECT id, app, name, applied FROM django_migrations WHERE app IN ('admin', 'intelligence') ORDER BY id")
    rows = cursor.fetchall()
    print('Current records:')
    for row in rows:
        print(row)
    
    # Get intelligence.0001_initial applied timestamp
    cursor.execute("SELECT applied FROM django_migrations WHERE app='intelligence' AND name='0001_initial'")
    result = cursor.fetchone()
    if not result:
        print("ERROR: intelligence.0001_initial not found in django_migrations")
        sys.exit(1)
    intel_time = result[0]
    
    # Get admin.0001_initial applied timestamp
    cursor.execute("SELECT applied FROM django_migrations WHERE app='admin' AND name='0001_initial'")
    result = cursor.fetchone()
    if not result:
        print("ERROR: admin.0001_initial not found in django_migrations")
        sys.exit(1)
    admin_time = result[0]
    
    print(f'intelligence.0001_initial applied: {intel_time}')
    print(f'admin.0001_initial applied: {admin_time}')
    
    if intel_time > admin_time:
        # Move intelligence to be slightly before admin
        new_time = admin_time - datetime.timedelta(seconds=1)
        cursor.execute(
            "UPDATE django_migrations SET applied=%s WHERE app='intelligence' AND name='0001_initial'",
            [new_time]
        )
        print(f'Updated intelligence.0001_initial applied time from {intel_time} to {new_time}')
    else:
        print('Order is already correct - intelligence is before admin')

print('Done')
