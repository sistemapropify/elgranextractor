import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import ejecutar_matching_requerimiento, guardar_resultados_matching
from requerimientos.models import Requerimiento

reqs = list(Requerimiento.objects.filter(
    tipo_propiedad__isnull=False
).exclude(
    tipo_propiedad='no_especificado'
).exclude(
    condicion='no_especificado'
).order_by('-fecha', '-hora')[:200])

print(f"Procesando {len(reqs)} requerimientos...")
for i, req in enumerate(reqs):
    try:
        resultados, stats = ejecutar_matching_requerimiento(req.id)
        if resultados:
            guardar_resultados_matching(req.id, resultados[:10])
        if (i+1) % 20 == 0:
            print(f"  {i+1}/{len(reqs)} procesados...")
    except Exception as e:
        print(f"  Error req {req.id}: {e}")

print("Completado")
