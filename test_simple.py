import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from propifai.models import PropifaiProperty

print("Test simple de conexion a Propifai")
print("==================================")

try:
    # Con using explícito
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"1. Count usando using('propifai'): {count}")
except Exception as e:
    print(f"1. ERROR con using: {e}")

try:
    # Sin using (depende del router)
    count2 = PropifaiProperty.objects.count()
    print(f"2. Count sin using: {count2}")
except Exception as e:
    print(f"2. ERROR sin using: {e}")

if count > 0:
    print("\n3. Primeras 3 propiedades:")
    props = PropifaiProperty.objects.using('propifai').all()[:3]
    for i, p in enumerate(props):
        print(f"   {i+1}. ID: {p.id}, Code: {p.code}, Dept: {p.department}, Price: {p.price}")
else:
    print("\n3. No hay propiedades en la tabla.")

print("\n==================================")
print("Resultado: La conexion a la base de datos Propifai " + ("FUNCIONA" if count > 0 else "NO FUNCIONA"))