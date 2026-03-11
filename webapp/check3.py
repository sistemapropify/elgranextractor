import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento

qs = Requerimiento.objects.order_by('-id')[:5]
for r in qs:
    print(r.id, r.requerimiento is not None, r.requerimiento[:20] if r.requerimiento else 'None')