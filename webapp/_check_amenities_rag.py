# -*- coding: utf-8 -*-
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

col = IntelligenceCollection.objects.get(name='propiedades_propify')
print('COLECCION:', col.name)
print('embedding_fields:', col.embedding_fields)
print('display_fields:', col.display_fields)
print('field_definitions keys:', list(col.field_definitions.keys()) if col.field_definitions else 'NONE')

if col.field_definitions:
    if 'amenities' in col.field_definitions:
        print('amenities SI esta en field_definitions')
    else:
        print('amenities NO esta en field_definitions')
else:
    print('field_definitions es None/vacio')

doc = IntelligenceDocument.objects.filter(collection=col).first()
if doc:
    print('\nDOCUMENTO RAG (primero):')
    print('  source_id:', doc.source_id)
    fv = doc.field_values or {}
    print('  field_values keys:', list(fv.keys()))
    if 'amenities' in fv:
        print('  amenities:', str(fv['amenities'])[:200])
    else:
        print('  amenities NO esta en field_values!')
    print('  content (primeros 300 chars):', str(doc.content)[:300] if doc.content else 'VACIO')
else:
    print('No hay documentos en la coleccion')

conn = connections['propifai']
with conn.cursor() as cursor:
    cursor.execute("SELECT TOP 3 codigo_unico_propiedad, amenities FROM [dbo].[properties] WHERE amenities IS NOT NULL AND amenities != ''")
    rows = cursor.fetchall()
    print('\nPROPIEDADES EN BD con amenities:')
    for r in rows:
        print(f'  {r[0]}: {str(r[1])[:200]}')
    
    cursor.execute("SELECT COUNT(*) FROM [dbo].[properties] WHERE amenities IS NOT NULL AND amenities != ''")
    total_con_amenities = cursor.fetchone()[0]
    print(f'Total propiedades con amenities en BD: {total_con_amenities}')
    
    cursor.execute("SELECT COUNT(*) FROM [dbo].[properties]")
    total = cursor.fetchone()[0]
    print(f'Total propiedades en BD: {total}')
