"""Script para actualizar embedding_fields y display_fields de la colección propiedades_propify."""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f'ANTES:')
print(f'  embedding_fields: {c.embedding_fields}')
print(f'  display_fields: {c.display_fields}')

# Actualizar embedding_fields para usar nombres resueltos (con _name) en lugar de IDs
c.embedding_fields = [
    'title', 'description', 'real_address', 'exact_address', 'coordinates',
    'district_name', 'condition_name', 'operation_type_name', 'property_type_name',
    'status_name', 'currency_name', 'amenities', 'project_name', 'source_url'
]

# Actualizar display_fields para usar nombres resueltos y eliminar duplicados
c.display_fields = [
    'title', 'description', 'delivery_date', 'price', 'maintenance_fee',
    'land_area', 'built_area', 'front_measure', 'depth_measure',
    'real_address', 'exact_address', 'coordinates', 'department',
    'district_name', 'urbanization', 'amenities', 'zoning',
    'parking_cost', 'project_name', 'ascensor', 'availability_status',
    'wp_slug', 'source', 'source_url', 'source_published_at',
    'condition_name', 'operation_type_name', 'property_type_name',
    'status_name', 'currency_name', 'bedrooms', 'bathrooms',
    'garage_spaces', 'floors'
]

c.save(update_fields=['embedding_fields', 'display_fields'])

# Verificar
c.refresh_from_db()
print(f'DESPUES:')
print(f'  embedding_fields: {c.embedding_fields}')
print(f'  display_fields: {c.display_fields}')
print('OK')
