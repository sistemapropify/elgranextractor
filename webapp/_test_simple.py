import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from intelligence.models import IntelligenceCollection

# Listar todas las colecciones
print("COLECCIONES DISPONIBLES:")
for c in IntelligenceCollection.objects.all():
    print(f"  - '{c.name}' (table: {c.table_name}, alias: {c.database_alias})")
