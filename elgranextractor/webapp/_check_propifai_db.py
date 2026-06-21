import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

with connections['propifai'].cursor() as cursor:
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
    tables = [r[0] for r in cursor.fetchall()]
    print("=== TABLAS EN BD PROPIFAI ===")
    for t in tables:
        print(f'  {t}')
    
    # Buscar tablas de distritos
    district_tables = [t for t in tables if 'district' in t.lower() or 'distrito' in t.lower()]
    print(f'\n=== TABLAS DE DISTRITOS: {district_tables} ===')
    for t in district_tables:
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{t}'")
        cols = [r[0] for r in cursor.fetchall()]
        print(f'  {t}: {cols}')
        cursor.execute(f"SELECT TOP 5 * FROM [{t}]")
        rows = cursor.fetchall()
        for row in rows:
            print(f'    {row}')
    
    # Ver columna district_fk_id en properties
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='properties'")
    cols = [r[0] for r in cursor.fetchall()]
    print(f'\n=== COLUMNAS DE PROPERTIES ({len(cols)}) ===')
    # Mostrar columnas relevantes
    relevant = [c for c in cols if any(k in c.lower() for k in ['district', 'distrito', 'name', 'title'])]
    print(f'  Relevantes: {relevant}')
