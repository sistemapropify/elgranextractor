"""Debug: check what property titles are available in IntelligenceDocument"""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

col = IntelligenceCollection.objects.filter(name='propiedadespropify').first()
print(f'Collection: {col}')
if col:
    total = IntelligenceDocument.objects.filter(collection=col).count()
    print(f'Total docs: {total}')
    
    # Show sample source_ids
    for doc in IntelligenceDocument.objects.filter(collection=col).only('source_id', 'field_values')[:5]:
        fv = doc.field_values or {}
        print(f'  sid={doc.source_id!r} title={fv.get("title","")!r} code={fv.get("code","")!r}')
    
    # Check if source_id='1' exists
    doc1 = IntelligenceDocument.objects.filter(collection=col, source_id='1').first()
    print(f'\nsource_id="1" exists: {doc1 is not None}')
    if doc1:
        fv = doc1.field_values or {}
        print(f'  title={fv.get("title","")!r} code={fv.get("code","")!r}')
    
    # Find numeric source_ids
    nums = []
    for d in IntelligenceDocument.objects.filter(collection=col).only('source_id')[:500]:
        try:
            int(d.source_id)
            nums.append(d.source_id)
        except:
            pass
    print(f'\nNumeric source_ids (first 10): {nums[:10]}')

# Check lead_properties for property IDs
try:
    with connections['propifai'].cursor() as c:
        c.execute("SELECT TOP 10 property_id, COUNT(*) FROM lead_properties GROUP BY property_id ORDER BY property_id")
        print(f'\nLead properties IDs:')
        for r in c.fetchall():
            print(f'  property_id={r[0]} ({type(r[0]).__name__}) count={r[1]}')
        
        # Check property table
        c.execute("SELECT TOP 5 id, code FROM property")
        print(f'\nProperty table sample:')
        for r in c.fetchall():
            print(f'  id={r[0]} code={r[1]!r}')
        
        # Check if property id=1 has code
        c.execute("SELECT id, code FROM property WHERE id = 1")
        r = c.fetchone()
        if r:
            print(f'\nProperty id=1: code={r[1]!r}')
except Exception as e:
    print(f'\nDB Error: {e}')
