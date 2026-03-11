import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import django
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento

last = Requerimiento.objects.order_by('-id')[:5]
for r in last:
    print(f"ID: {r.id}, Creado: {r.creado_en}")
    if r.requerimiento:
        print(f"  Requerimiento (primeros 100 chars): {r.requerimiento[:100]}")
    else:
        print(f"  Requerimiento: VACÍO")
    print()