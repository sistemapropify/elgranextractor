import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ.setdefault('PROPIFAI_DB_NAME', 'dbpropify_be')
import django; django.setup()
from django.conf import settings

db = settings.DATABASES['default']
print("=== CONEXION DEFAULT ===")
print(f"Servidor: {db.get('HOST')}")
print(f"Base: {db.get('NAME')}")
print(f"Usuario: {db.get('USER')}")
print(f"Puerto: {db.get('PORT')}")
print(f"Engine: {db.get('ENGINE')}")

db2 = settings.DATABASES.get('propifai', {})
print()
print("=== CONEXION PROPIFAI ===")
print(f"Servidor: {db2.get('HOST')}")
print(f"Base: {db2.get('NAME')}")
print(f"Usuario: {db2.get('USER')}")
print(f"Puerto: {db2.get('PORT')}")
