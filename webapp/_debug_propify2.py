import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, os.path.dirname(__file__))
import django; django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

c = IntelligenceCollection.objects.get(name='propiedadespropify')

print(f"=== COLECCIÓN ===")
print(f"Table: {c.table_name}")
print(f"DB alias: {c.database_alias}")
print(f"Source SQL: {c.source_sql}")
print(f"Last sync at: {c.last_sync_at}")
print(f"Last sync count: {c.last_sync_count}")

# Docs en RAG
docs = IntelligenceDocument.objects.filter(collection=c)
print(f"\n=== DOCUMENTOS RAG ===")
print(f"Total: {docs.count()}")
print(f"Con embedding: {docs.filter(embedding__isnull=False).count()}")

rag_ids = set(int(d.source_id) for d in docs if d.source_id.isdigit())
print(f"IDs numéricos en RAG: {len(rag_ids)}")
if rag_ids:
    print(f"Rango IDs RAG: {min(rag_ids)} - {max(rag_ids)}")

# Consultar tabla property en BD propifai
print(f"\n=== TABLA ORIGEN (propifai.property) ===")
conn = connections['propifai']
with conn.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM [dbo].[property]")
    total = cursor.fetchone()[0]
    print(f"Total registros: {total}")
    
    cursor.execute("SELECT TOP 10 id FROM [dbo].[property] ORDER BY id DESC")
    ultimos_ids = [str(row[0]) for row in cursor.fetchall()]
    print(f"Últimos 10 IDs en BD: {ultimos_ids}")
    
    # IDs en BD que NO están en RAG
    cursor.execute("SELECT id FROM [dbo].[property]")
    todos_ids_bd = set(str(row[0]) for row in cursor.fetchall())
    faltan = todos_ids_bd - set(d.source_id for d in docs)
    print(f"\nIDs en BD que NO están en RAG: {len(faltan)}")
    
    # Convertir a enteros para ordenar
    faltan_nums = sorted([int(x) for x in faltan if x.isdigit()])
    if faltan_nums:
        print(f"Faltantes IDs: {faltan_nums[:20]}...")
        print(f"Rango faltantes: {min(faltan_nums)} - {max(faltan_nums)}")
    
    # Verificar si hay created_at filtrado
    cursor.execute("SELECT TOP 3 id, created_at FROM [dbo].[property] ORDER BY id DESC")
    print(f"\nÚltimos 3 registros en BD:")
    for row in cursor.fetchall():
        en_rag = "✅ EN RAG" if str(row[0]) in rag_ids else "❌ FALTA"
        print(f"  ID={row[0]} | created_at={row[1]} | {en_rag}")
