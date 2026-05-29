import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()
from agentes.models import Agente
import json

agentes_qs = list(Agente.objects.all().values('id', 'nombre_completo'))
print(f"Total agentes: {len(agentes_qs)}")
for a in agentes_qs[:5]:
    print(f"  id={a['id']}, nombre={repr(a['nombre_completo'])}")

# Test the JSON
agentes_map = {}
for a in agentes_qs:
    nombre_key = a['nombre_completo'].lower().strip()
    agentes_map[nombre_key] = a['id']

json_str = json.dumps(agentes_map, ensure_ascii=False)
print(f"\nJSON length: {len(json_str)}")
print(f"JSON sample: {json_str[:200]}")
