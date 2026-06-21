import os
import sys
import django

# Agregar el directorio webapp al path
sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection

try:
    c = IntelligenceCollection.objects.get(name='propiedades_propify')
    print(f'Nombre: {c.name}')
    print(f'Tabla: {c.table_name}')
    print(f'Descripción: {c.description}')
    print(f'Nivel acceso: {c.access_level}')
    print(f'Activa: {c.is_active}')
    print(f'Última sync: {c.last_sync_at}')
    print(f'Count: {c.last_sync_count}')
    print(f'Campos embedding: {c.embedding_fields}')
    print(f'Campos display: {c.display_fields}')
    print(f'Campos filtro: {c.filter_fields}')
    if c.field_definitions:
        print(f'Definiciones campos ({len(c.field_definitions)}):')
        for key in list(c.field_definitions.keys())[:5]:  # Mostrar primeros 5
            print(f'  - {key}: {c.field_definitions[key]}')
    else:
        print('Definiciones campos: None')
        
    # Verificar documentos
    from intelligence.models import IntelligenceDocument
    docs = IntelligenceDocument.objects.filter(collection=c)
    print(f'\nDocumentos en colección: {docs.count()}')
    if docs.exists():
        doc = docs.first()
        print(f'Primer documento - Source ID: {doc.source_id}')
        print(f'Campos: {list(doc.field_values.keys()) if doc.field_values else "None"}')
        
except IntelligenceCollection.DoesNotExist:
    print('Colección propiedades_propify no encontrada')
except Exception as e:
    print(f'Error: {e}')