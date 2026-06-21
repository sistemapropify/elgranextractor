import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import ejecutar_matching_requerimiento
from matching.serializers import MatchingResultSerializer

req_id = 24304
resultados, stats = ejecutar_matching_requerimiento(req_id)
print(f"Resultados: {len(resultados)}")

# Intentar serializar
try:
    serializer = MatchingResultSerializer(resultados, many=True)
    data = serializer.data
    print(f"Serializados OK: {len(data)}")
except Exception as e:
    print(f"Error serializando: {e}")
    import traceback
    traceback.print_exc()
