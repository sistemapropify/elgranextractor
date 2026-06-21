import os, sys
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
).order_by('-fecha', '-hora')[:50])

import time
for req in reqs:
    try:
        resultados, stats = ejecutar_matching_requerimiento(req.id)
        if resultados:
            guardar_resultados_matching(req.id, resultados[:10])
        print(f"OK req {req.id}: {len(resultados)} matches")
    except Exception as e:
        print(f"ERR req {req.id}: {e}")
