import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

# Probar consulta directa para ver tablas
with connections['default'].cursor() as cursor:
    # Buscar tablas que podrian ser de distritos
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
    tables = [r[0] for r in cursor.fetchall()]
    print("=== TABLAS EN AZURE SQL ===")
    for t in tables:
        print(f'  {t}')
    
    print("\n=== TABLAS CON 'district' O 'distrito' ===")
    district_tables = [t for t in tables if 'district' in t.lower() or 'distrito' in t.lower()]
    for t in district_tables:
        print(f'  {t}')
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{t}'")
        cols = [r[0] for r in cursor.fetchall()]
        print(f'    Columnas: {cols}')
        cursor.execute(f"SELECT TOP 5 * FROM [{t}]")
        rows = cursor.fetchall()
        for row in rows:
            print(f'    {row}')
