import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from propifai.models import PropifaiProperty

# Obtener las primeras 10 propiedades ordenadas por created_at descendente
props = PropifaiProperty.objects.all().order_by('-created_at')[:10]
print("Propiedades más recientes (ordenadas por created_at descendente):")
for p in props:
    print(f"{p.code}: {p.created_at}")

print("\n---")

# Obtener las primeras 10 propiedades ordenadas por created_at ascendente (más antiguas)
props_old = PropifaiProperty.objects.all().order_by('created_at')[:10]
print("Propiedades más antiguas (ordenadas por created_at ascendente):")
for p in props_old:
    print(f"{p.code}: {p.created_at}")