import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()
from django.db import connections

conn = connections['propifai']
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM property')
print('Total property:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM property WHERE is_visible=1')
print('Visible:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM property_specs')
print('Total property_specs:', cursor.fetchone()[0])

cursor.execute('SELECT id, name FROM property_type')
print('property_type:')
for r in cursor.fetchall():
    print('  id=' + str(r[0]) + ' name=' + str(r[1]))

cursor.execute('SELECT id, name FROM property_condition')
print('property_condition:')
for r in cursor.fetchall():
    print('  id=' + str(r[0]) + ' name=' + str(r[1]))

cursor.execute('SELECT id, code, name FROM currency')
print('currency:')
for r in cursor.fetchall():
    print('  id=' + str(r[0]) + ' code=' + str(r[1]) + ' name=' + str(r[2]))

cursor.execute('SELECT id, name FROM operation_type')
print('operation_type:')
for r in cursor.fetchall():
    print('  id=' + str(r[0]) + ' name=' + str(r[1]))

cursor.execute('SELECT TOP 5 id, name FROM district')
print('district sample:')
for r in cursor.fetchall():
    print('  id=' + str(r[0]) + ' name=' + str(r[1]))

cursor.close()
conn.close()
