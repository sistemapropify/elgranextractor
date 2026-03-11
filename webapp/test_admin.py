import os
import django
import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

print("Probando acceso al admin...")
try:
    # Intentar obtener un objeto
    obj = PropiedadRaw.objects.first()
    if obj:
        print(f"ID: {obj.id}")
        print(f"Fecha publicación: {obj.fecha_publicacion} (tipo: {type(obj.fecha_publicacion)})")
        print(f"¿Es datetime.date? {isinstance(obj.fecha_publicacion, (type(None), datetime.date))}")
    else:
        print("No hay objetos")
except Exception as e:
    print(f"Error al obtener objeto: {e}")
    import traceback
    traceback.print_exc()

# Verificar si el admin puede listar
from django.contrib.admin.sites import site
from ingestas.admin import PropiedadRawAdmin
print("\nVerificando admin registration...")
try:
    admin = site._registry[PropiedadRaw]
    print(f"Admin registrado: {admin}")
except Exception as e:
    print(f"Error en admin: {e}")