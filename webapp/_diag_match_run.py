import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import ejecutar_matching_requerimiento
from requerimientos.models import Requerimiento

req = Requerimiento.objects.filter(
    tipo_propiedad__isnull=False
).exclude(
    tipo_propiedad='no_especificado'
).exclude(
    condicion='no_especificado'
).first()

if not req:
    print("No hay requerimientos")
    sys.exit(1)

print(f"Ejecutando matching para req #{req.id}: {req.tipo_propiedad}, {req.condicion}, {req.distritos}, {req.presupuesto_monto} {req.presupuesto_moneda}")

resultados, stats = ejecutar_matching_requerimiento(req.id)

print(f"Estadisticas: {stats}")
print(f"Total resultados: {len(resultados)}")
if resultados:
    top = resultados[0]
    print(f"Top match: propiedad_id={top['propiedad_id']}, score={top['score_total']}")
    print(f"Score detalle: {top['score_detalle']}")
else:
    print("Sin resultados compatibles")
