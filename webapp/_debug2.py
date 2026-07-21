import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
django.setup()
from django.db import connections

with connections['propifai'].cursor() as c:
    c.execute('SELECT DISTINCT TOP 5 lp.property_id FROM lead_properties lp ORDER BY lp.property_id')
    print('Lead IDs:', [r[0] for r in c.fetchall()])
    
    c.execute('SELECT id, code, title FROM property WHERE id IN (6, 19, 25, 34, 36)')
    print('Property table:')
    for r in c.fetchall():
        print(f'  id={r[0]} code={repr(r[1])} title={repr(r[2])[:80]}')
