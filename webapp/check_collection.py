import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()
from intelligence.models import IntelligenceCollection
from django.shortcuts import get_object_or_404

try:
    collection = IntelligenceCollection.objects.get(id='b899d903-5a14-4b23-b567-6bf15aa5f5b9')
    print(f'Nombre: {collection.name}')
    print(f'SQL: {collection.source_sql[:200]}...')
    print(f'Campos embedding: {collection.embedding_fields}')
    print(f'Tabla referenciada (aproximación):')
    # Buscar el nombre de tabla en el SQL
    sql_lower = collection.source_sql.lower()
    if 'from' in sql_lower:
        # Extraer tabla después de FROM
        from_pos = sql_lower.find('from')
        rest = sql_lower[from_pos+4:].strip()
        # Tomar primera palabra después de FROM
        table_name = rest.split()[0].strip('[]`"\'')
        print(f'  Posible tabla: {table_name}')
except IntelligenceCollection.DoesNotExist:
    print('Colección no encontrada')
except Exception as e:
    print(f'Error: {e}')