"""
Script para debuggear _get_columns_flexible
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from django.db import connections
from intelligence.services.schema_discovery import SchemaDiscoveryService

output = []

# 1. Probar get_table_columns directo con propifai_propiedad en BD propifai
output.append("=== get_table_columns('propifai_propiedad', 'dbo', 'propifai') ===")
try:
    cols = SchemaDiscoveryService.get_table_columns('propifai_propiedad', 'dbo', 'propifai')
    output.append(f"Columnas encontradas: {len(cols)}")
    for c in cols:
        output.append(f"  - {c.get('name')}")
except Exception as e:
    output.append(f"ERROR: {e}")

# 2. Probar get_table_columns directo con propifai_propiedad en BD default
output.append("\n=== get_table_columns('propifai_propiedad', 'dbo', 'default') ===")
try:
    cols = SchemaDiscoveryService.get_table_columns('propifai_propiedad', 'dbo', 'default')
    output.append(f"Columnas encontradas: {len(cols)}")
    for c in cols:
        output.append(f"  - {c.get('name')}")
except Exception as e:
    output.append(f"ERROR: {e}")

# 3. Probar _get_columns_flexible
output.append("\n=== _get_columns_flexible('propifai_propiedad', 'dbo', 'propifai', ['default']) ===")
try:
    cols, alias = SchemaDiscoveryService._get_columns_flexible(
        'propifai_propiedad', 'dbo', 'propifai', ['default']
    )
    output.append(f"Columnas encontradas: {len(cols)} en BD: {alias}")
    for c in cols:
        output.append(f"  - {c.get('name')}")
except Exception as e:
    import traceback
    output.append(f"ERROR: {e}")
    output.append(traceback.format_exc())

# 4. Ver qué conexiones están disponibles
output.append("\n=== CONEXIONES DISPONIBLES ===")
for alias in connections.databases:
    output.append(f"  - {alias}")

output_path = os.path.join(os.path.dirname(__file__), '_debug_fk_output4.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"Output escrito a {output_path}")
