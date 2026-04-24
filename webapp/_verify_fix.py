import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')
print("source_sql:", c.source_sql)
print("embedding_fields:", c.embedding_fields)
print("display_fields has district_name:", 'district_name' in c.display_fields)
