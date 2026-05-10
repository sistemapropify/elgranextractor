"""
Script para verificar que detect_foreign_keys ahora funciona con propifai_propiedad
usando el fallback a BD default
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

from intelligence.services.schema_discovery import SchemaDiscoveryService

output = []

# 1. Probar detect_foreign_keys con 'propifai_propiedad' (nombre Django) en BD 'propifai'
output.append("=== DETECT FOREIGN KEYS para 'propifai_propiedad' (BD propifai, con fallback) ===")
try:
    fks = SchemaDiscoveryService.detect_foreign_keys('propifai_propiedad', 'dbo', 'propifai')
    output.append(json.dumps(fks, indent=2, default=str))
except Exception as e:
    import traceback
    output.append(f"ERROR: {e}")
    output.append(traceback.format_exc())

# 2. Verificar que garage_type_id está en las FK detectadas
output.append("\n=== BUSCANDO garage_type_id EN FK ===")
try:
    fks = SchemaDiscoveryService.detect_foreign_keys('propifai_propiedad', 'dbo', 'propifai')
    garage_fk = [fk for fk in fks if 'garage' in fk.get('column', '').lower()]
    if garage_fk:
        output.append(f"¡ENCONTRADO! garage_type_id detectado:")
        output.append(json.dumps(garage_fk, indent=2, default=str))
    else:
        output.append("NO ENCONTRADO - garage_type_id no está en las FK detectadas")
        # Mostrar todas las FK para diagnóstico
        output.append("Todas las FK detectadas:")
        for fk in fks:
            output.append(f"  - {fk.get('column')} -> {fk.get('referenced_table')}")
except Exception as e:
    output.append(f"ERROR: {e}")

output_path = os.path.join(os.path.dirname(__file__), '_debug_fk_output3.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"Output escrito a {output_path}")
