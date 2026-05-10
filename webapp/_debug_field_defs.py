"""
Debug: ver estructura de field_definitions de la colección.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection

collection = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f'field_definitions type: {type(collection.field_definitions)}')
print(f'field_definitions: {collection.field_definitions}')
print(f'\nembedding_fields: {collection.embedding_fields}')
print(f'display_fields: {collection.display_fields}')
print(f'filter_fields: {collection.filter_fields}')
print(f'\nsource_sql: {collection.source_sql}')
