"""Script para limpiar campos duplicados de los documentos existentes.
Elimina campos como condition_name_description, condition_name_name, district_name_code, etc.
y deja solo el valor principal (condition_name, district_name, etc.)."""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from intelligence.models import IntelligenceDocument

docs = IntelligenceDocument.objects.filter(collection__name='propiedades_propify')
total = docs.count()
print(f'Procesando {total} documentos...')

cleaned = 0
for doc in docs:
    fv = doc.field_values or {}
    if not fv:
        continue
    
    # Identificar campos duplicados: pattern {resolved_key}_{display_field}
    # donde resolved_key ya existe como campo principal
    keys_to_remove = []
    for k in list(fv.keys()):
        # Eliminar patrones como condition_name_name, condition_name_description, district_name_code, etc.
        # pero CONSERVAR condition_name, district_name, etc.
        if k.endswith('_name_name') or k.endswith('_name_description') or k.endswith('_name_code') or k.endswith('_name_symbol'):
            keys_to_remove.append(k)
        elif k.endswith('_name_first_name') or k.endswith('_name_last_name') or k.endswith('_name_username') or k.endswith('_name_maternal_last_name'):
            keys_to_remove.append(k)
    
    if keys_to_remove:
        for k in keys_to_remove:
            del fv[k]
        doc.field_values = fv
        doc.save(update_fields=['field_values'])
        cleaned += 1
        if cleaned <= 5:
            print(f'  Doc {doc.source_id}: eliminados {len(keys_to_remove)} campos duplicados')

print(f'\nTotal: {cleaned} documentos limpiados')
