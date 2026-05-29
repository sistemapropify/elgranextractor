import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import ejecutar_matching_requerimiento, guardar_resultados_matching

# Probar con req 24304
req_id = 24304
print(f"Ejecutando matching para req {req_id}...")
resultados, stats = ejecutar_matching_requerimiento(req_id)
print(f"Resultados: {len(resultados)}")
if resultados:
    for r in resultados[:5]:
        print(f"  prop_id={r['propiedad_id']}, score={r['score_total']}, detalle={r['score_detalle']}")
else:
    print("Sin resultados - guardando de todas formas")
    print(f"Stats: {stats}")

# Guardar
guardar_resultados_matching(req_id, resultados)
print("Guardado OK")
