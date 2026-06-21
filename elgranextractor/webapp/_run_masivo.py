import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import ejecutar_matching_masivo

resultados = ejecutar_matching_masivo(limite_por_requerimiento=10)
print(f"Matching masivo completado. {len(resultados)} requerimientos procesados.")
for req_id, info in list(resultados.items())[:5]:
    print(f"  req {req_id}: score={info['mejor_score']}, compatibles={info['total_compatibles']}")
