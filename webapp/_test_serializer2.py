import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import ejecutar_matching_requerimiento
from matching.serializers import MatchingResultSerializer

req_id = 20412
resultados, stats = ejecutar_matching_requerimiento(req_id)
print(f"Resultados: {len(resultados)}")

serializer = MatchingResultSerializer(resultados, many=True)
data = serializer.data
print(f"Serializados: {len(data)}")
if data:
    print(f"Primero: {data[0]}")
