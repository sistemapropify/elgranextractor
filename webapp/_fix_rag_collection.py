import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')

# 1. Actualizar source_sql para incluir JOIN con properties_district
old_sql = c.source_sql
new_sql = """SELECT p.*, d.name as district_name 
FROM properties p 
LEFT JOIN properties_district d ON p.district = d.id"""

print(f"SQL anterior: {old_sql}")
print(f"SQL nuevo: {new_sql}")

c.source_sql = new_sql

# 2. Agregar district_name a embedding_fields si no está
old_embedding = c.embedding_fields
print(f"\nEmbedding fields anterior: {old_embedding}")

if 'district_name' not in c.embedding_fields:
    c.embedding_fields = c.embedding_fields + ['district_name']
    
print(f"Embedding fields nuevo: {c.embedding_fields}")

# 3. Agregar district_name a display_fields si no está
if 'district_name' not in c.display_fields:
    c.display_fields = c.display_fields + ['district_name']

# 4. Guardar cambios
c.save()
print("\n✅ Colección actualizada exitosamente")
print(f"   source_sql: {c.source_sql}")
print(f"   embedding_fields: {c.embedding_fields}")
