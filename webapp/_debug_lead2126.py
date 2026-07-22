import os; os.environ['DJANGO_SETTINGS_MODULE']='settings'; os.environ.setdefault('PROPIFAI_DB_NAME','dbpropify_be')
import django; django.setup()
from django.db import connections

conn = connections['propifai']
with conn.cursor() as c:
    # Ver si hay eventos para lead_id=2126
    c.execute("SELECT id, lead_id, title, start_time, is_active FROM event WHERE lead_id = 2126")
    rows = c.fetchall()
    print(f"Eventos para lead_id=2126: {len(rows)}")
    for r in rows:
        print(f"  id={r[0]} lead_id={r[1]} title={r[2]} start={r[3]} is_active={r[4]}")
    
    # Ver status del lead 2126
    c.execute("SELECT id, lead_status_id FROM lead WHERE id = 2126")
    r2 = c.fetchone()
    if r2:
        print(f"\nLead 2126: lead_status_id={r2[1]}")
        c.execute("SELECT id, name FROM lead_status WHERE id = %s", r2[1])
        r3 = c.fetchone()
        if r3:
            print(f"  Status name: {r3[1]}")
