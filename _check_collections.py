import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.chdir('webapp')
django.setup()
from intelligence.models import IntelligenceCollection
cols = IntelligenceCollection.objects.all()
for c in cols:
    print(f"  {c.name}: {c.description}")
print(f"Total: {cols.count()}")
