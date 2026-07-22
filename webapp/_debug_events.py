import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ.setdefault('PROPIFAI_DB_NAME', 'dbpropify_be')
django.setup()

from django.db import connections

# 1. Verificar a qué base de datos apunta 'propifai'
conn = connections['propifai']
with conn.cursor() as c:
    c.execute('SELECT DB_NAME()')
    print(f"Base de datos actual (propifai): {c.fetchone()[0]}")

    # 2. Buscar la tabla events
    c.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'events'")
    rows = c.fetchall()
    if rows:
        for r in rows:
            print(f"Tabla events encontrada: {r}")
    else:
        print("NO existe 'events' en INFORMATION_SCHEMA")
        # 3. Buscar cualquier tabla que empiece con 'event'
        c.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'event%'")
        r2 = c.fetchall()
        if r2:
            for r in r2:
                print(f"Tabla LIKE 'event%': {r}")
        else:
            print("No hay tablas LIKE 'event%'")
            # 4. Mostrar las primeras 10 tablas como referencia
            c.execute("SELECT TOP 10 TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME")
            for r in c.fetchall():
                print(f"  Tabla ref: {r}")

    # 5. Ver qué tablas tienen lead_id
    c.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME = 'lead_id'")
    lead_tables = c.fetchall()
    if lead_tables:
        print(f"\nTablas con columna 'lead_id':")
        for r in lead_tables:
            print(f"  {r}")
    else:
        print("\nNo hay tablas con columna 'lead_id'")
