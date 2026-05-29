import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.models import MatchResult
from matching.engine import ejecutar_matching_requerimiento, guardar_resultados_matching

# Buscar req con matches existentes
ultimos = MatchResult.objects.filter(fase_eliminada__isnull=True).order_by('-ejecutado_en')[:3]
print("Últimos 3 matches existentes:")
for m in ultimos:
    print(f"  req_id={m.requerimiento_id}, prop_id={m.propiedad_id}, score={m.score_total}")

# Tomar el primero
if ultimos:
    req_id = ultimos[0].requerimiento_id
    print(f"\nRe-ejecutando matching para req {req_id}")
    resultados, stats = ejecutar_matching_requerimiento(req_id)
    print(f"Resultados: {len(resultados)} compatibles")
    if resultados:
        top = resultados[0]
        print(f"Top: prop_id={top['propiedad_id']}, score={top['score_total']}, detalle={top['score_detalle']}")
    guardar_resultados_matching(req_id, resultados)
    print("Guardado")
