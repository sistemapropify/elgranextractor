# -*- coding: utf-8 -*-
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

conn = connections['propifai']
col = IntelligenceCollection.objects.get(name='propiedades_propify')

print("=" * 80)
print("1. VERIFICAR SI PROPIEDAD LG835530090 ESTA EN RAG")
print("=" * 80)

# Buscar en RAG por source_id
# Primero, encontrar el id en la BD
with conn.cursor() as cursor:
    cursor.execute("SELECT id FROM [dbo].[properties] WHERE codigo_unico_propiedad = 'LG835530090'")
    row = cursor.fetchone()
    if row:
        prop_id = row[0]
        print(f"ID en BD properties: {prop_id}")
        
        # Buscar en documentos RAG
        docs = IntelligenceDocument.objects.filter(collection=col, source_id=str(prop_id))
        if docs.exists():
            doc = docs.first()
            print(f"SI esta en RAG! Documento ID: {doc.id}")
            fv = doc.field_values or {}
            print(f"  title: {fv.get('title', 'N/A')}")
            print(f"  description (primeros 500): {str(fv.get('description', ''))[:500]}")
            print(f"  amenities: '{fv.get('amenities', '')}'")
            print(f"  content (primeros 500): {str(doc.content)[:500] if doc.content else 'VACIO'}")
        else:
            print(f"NO esta en RAG! (buscando source_id='{prop_id}')")
            
            # Ver cuantos documentos hay y que source_ids tienen
            total_docs = IntelligenceDocument.objects.filter(collection=col).count()
            print(f"Total documentos en RAG: {total_docs}")
            
            # Ver source_ids
            all_ids = IntelligenceDocument.objects.filter(collection=col).values_list('source_id', flat=True)[:10]
            print(f"Primeros 10 source_ids: {list(all_ids)}")
    else:
        print("Propiedad no encontrada en BD properties por codigo_unico_propiedad")
        # Buscar por codigo interno
        cursor.execute("SELECT id FROM [dbo].[properties] WHERE code = 'PROP000050'")
        row = cursor.fetchone()
        if row:
            print(f"Encontrada por code='PROP000050', id={row[0]}")

print("\n" + "=" * 80)
print("2. VER TODAS LAS PROPIEDADES EN BD (primeros 20)")
print("=" * 80)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT TOP 20 id, codigo_unico_propiedad, code, title, 
               CASE WHEN LEN(description) > 100 THEN LEFT(description, 100) + '...' ELSE description END as desc_short
        FROM [dbo].[properties] 
        ORDER BY id
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(f"  ID={r[0]}, codigo={r[1]}, code={r[2]}, title={r[3][:60] if r[3] else 'NULL'}")

print("\n" + "=" * 80)
print("3. VER source_ids EN RAG vs IDs EN BD")
print("=" * 80)

rag_ids = set(IntelligenceDocument.objects.filter(collection=col).values_list('source_id', flat=True))
print(f"Source IDs en RAG ({len(rag_ids)}): {sorted([int(x) for x in rag_ids])[:20]}...")

with conn.cursor() as cursor:
    cursor.execute("SELECT id FROM [dbo].[properties] ORDER BY id")
    bd_ids = set([r[0] for r in cursor.fetchall()])
    print(f"IDs en BD ({len(bd_ids)}): {sorted(bd_ids)[:20]}...")
    
    missing = bd_ids - set(int(x) for x in rag_ids)
    if missing:
        print(f"\nIDs en BD que NO estan en RAG ({len(missing)}): {sorted(missing)[:20]}")
    else:
        print("\nTODOS los IDs de BD estan en RAG")

print("\nDIAGNOSTICO COMPLETADO")
