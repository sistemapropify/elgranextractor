"""
Script para sincronizar la colección propiedades_propify con datos reales.
"""
import sys
import os
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

# Verificar estado actual
print('=== ESTADO ACTUAL ===')
collection = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f'  database_alias: {collection.database_alias}')
print(f'  table_name: {collection.table_name}')
print(f'  Documentos actuales: {IntelligenceDocument.objects.filter(collection=collection).count()}')

# Ver datos en tabla properties
print('\n=== DATOS EN TABLA PROPERTIES ===')
conn = connections['propifai']
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM properties')
count = cursor.fetchone()[0]
print(f'  Total registros: {count}')

# Ver muestra
cursor.execute('SELECT TOP 3 id, title, price, currency_id, district, urbanization FROM properties')
cols = [col[0] for col in cursor.description]
for row in cursor.fetchall():
    print(f'  {dict(zip(cols, row))}')
cursor.close()

# Sincronizar
print('\n=== SINCRONIZANDO ===')
from intelligence.services.rag import RAGService

success, message, stats = RAGService.sync_collection_dynamic(
    collection_name='propiedades_propify',
    force_full_sync=True,
    database_alias='propifai'
)

print(f'  Success: {success}')
print(f'  Message: {message}')
print(f'  Stats: {stats}')

# Verificar documentos creados
print('\n=== DOCUMENTOS CREADOS ===')
doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
print(f'  Total documentos: {doc_count}')

if doc_count > 0:
    docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
    for doc in docs:
        fv = doc.field_values or {}
        print(f'  source_id={doc.source_id}, title={fv.get("title", "N/A")}, price={fv.get("price", "N/A")}')

print('\n=== HECHO ===')
