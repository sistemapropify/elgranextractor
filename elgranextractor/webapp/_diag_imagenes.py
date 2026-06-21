import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()
from django.db import connections

with connections['propifai'].cursor() as cursor:
    # Buscar tablas relacionadas a imágenes
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' AND TABLE_NAME LIKE '%image%' OR TABLE_NAME LIKE '%media%' OR TABLE_NAME LIKE '%photo%'")
    print("Tablas de imágenes:")
    for r in cursor.fetchall():
        print(f"  {r[0]}")
    
    # Ver columnas de property_media
    cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'property_media'")
    print("\nColumnas de property_media:")
    for r in cursor.fetchall():
        print(f"  {r[0]} ({r[1]})")
    
    # Ver columnas de property_images si existe
    cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'property_images'")
    rows = cursor.fetchall()
    if rows:
        print("\nColumnas de property_images:")
        for r in rows:
            print(f"  {r[0]} ({r[1]})")
    
    # Muestra algunos registros de property_media
    cursor.execute("SELECT TOP 5 * FROM property_media")
    cols = [desc[0] for desc in cursor.description]
    print(f"\nMuestra property_media ({len(cols)} columnas):")
    for r in cursor.fetchall():
        for i, c in enumerate(cols):
            print(f"  {c}: {r[i]}")
        print("  ---")
    
    # Ver si property tiene campo de imagen directo
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'property' AND (COLUMN_NAME LIKE '%image%' OR COLUMN_NAME LIKE '%img%' OR COLUMN_NAME LIKE '%photo%' OR COLUMN_NAME LIKE '%picture%' OR COLUMN_NAME LIKE '%url%' OR COLUMN_NAME LIKE '%media%')")
    cols = cursor.fetchall()
    if cols:
        print("\nColumnas de imagen en property:")
        for c in cols:
            print(f"  {c[0]}")
