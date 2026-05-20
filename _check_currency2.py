import sys, os, django
sys.path.insert(0, 'd:\\proyectos\\prometeo\\webapp')
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
django.setup()

from propifai.models import PropifaiProperty
from django.db.models import Count

# Distribucion de currency_id
print('=== DISTRIBUCION CURRENCY_ID ===')
for row in PropifaiProperty.objects.values('currency_id').annotate(total=Count('id')).order_by('currency_id'):
    print(f'  currency_id={row["currency_id"]}: {row["total"]} props')

# Top 5 PEN
print('\n=== TOP 5 PEN (currency_id=2) ===')
for p in PropifaiProperty.objects.filter(currency_id=2).order_by('-price')[:5]:
    print(f'  {p.code}: {p.price} - {p.title}')

# Top 5 USD
print('\n=== TOP 5 USD (currency_id=1) ===')
for p in PropifaiProperty.objects.filter(currency_id=1).order_by('-price')[:5]:
    print(f'  {p.code}: {p.price} - {p.title}')

# Sin currency_id
print('\n=== SIN CURRENCY_ID (null) ===')
total_null = PropifaiProperty.objects.filter(currency_id__isnull=True).count()
print(f'  Total: {total_null}')
if total_null > 0:
    for p in PropifaiProperty.objects.filter(currency_id__isnull=True)[:3]:
        print(f'  {p.code}: {p.price} - {p.title}')
