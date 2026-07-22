import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
django.setup()
from django.db import connections
with connections['propifai'].cursor() as c:
    c.execute('SELECT TOP 3 id, status, username, source FROM lead ORDER BY id')
    print('Lead columns check:')
    for r in c.fetchall():
        print(f'  id={r[0]} status={repr(r[1])} username={r[2]} source={r[3]}')
