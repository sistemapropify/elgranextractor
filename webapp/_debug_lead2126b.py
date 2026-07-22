import os; os.environ['DJANGO_SETTINGS_MODULE']='settings'; os.environ.setdefault('PROPIFAI_DB_NAME','dbpropify_be')
import django; django.setup()
from django.db import connections

conn = connections['propifai']
with conn.cursor() as c:
    # Ver el evento 755
    c.execute("SELECT id, lead_id, title, start_time, is_active FROM event WHERE id = 755")
    r = c.fetchone()
    if r:
        print(f"Evento 755: lead_id={r[1]} title={r[2]} start={r[3]} is_active={r[4]}")
    else:
        print("Evento 755 NO ENCONTRADO")
    
    # Ver status_id=14
    c.execute("SELECT id, name FROM lead_status WHERE id = 14")
    r2 = c.fetchone()
    print(f"lead_status 14: {r2}")
    
    # Ver qué status_name tiene lead_status_id=14
    c.execute("SELECT id, name FROM lead_status ORDER BY id")
    for r3 in c.fetchall():
        print(f"  lead_status {r3[0]}: {r3[1]}")
    
    # Ver cuántos eventos tienen lead_id=2126
    c.execute("SELECT COUNT(*) FROM event WHERE lead_id = 2126")
    print(f"Eventos con lead_id=2126: {c.fetchone()[0]}")
    
    # Ver todos los event_type_id
    c.execute("SELECT DISTINCT event_type_id FROM event WHERE lead_id = 2126")
    types = c.fetchall()
    print(f"event_type_ids para lead 2126: {[r[0] for r in types]}")
