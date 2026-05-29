import django, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, '.')
django.setup()

from requerimientos.models import Requerimiento

enero = Requerimiento.objects.filter(fecha__year=2026, fecha__month=1)
total = enero.count()
print(f"Enero 2026: {total} registros")

enero.delete()
print(f"OK - {total} registros de enero 2026 borrados")
