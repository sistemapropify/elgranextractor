#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from analisis_crm.models import Lead
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate

print("=== DEBUG LEADS ===")

# Verificar total de leads
total = Lead.objects.count()
print(f"Total leads en la base de datos: {total}")

# Verificar algunos leads con date_entry
leads_with_date = Lead.objects.filter(date_entry__isnull=False).count()
print(f"Leads con date_entry no nulo: {leads_with_date}")

if leads_with_date > 0:
    # Mostrar algunos date_entry
    sample = Lead.objects.filter(date_entry__isnull=False).values('date_entry')[:5]
    for s in sample:
        print(f"  date_entry: {s['date_entry']}")

# Calcular mes actual
now = timezone.now()
first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
print(f"\nMes actual: {first_day_of_month.date()} a {now.date()}")

# Consulta diaria
daily_leads = Lead.objects.filter(
    date_entry__gte=first_day_of_month,
    date_entry__lte=now
).annotate(
    day=TruncDate('date_entry')
).values('day').annotate(
    count=Count('id')
).order_by('day')

print(f"\nLeads agrupados por día (raw query count): {daily_leads.count()}")
for entry in daily_leads:
    print(f"  {entry['day']}: {entry['count']}")

# Generar días del mes
days_of_month = []
counts_per_day = []
current_day = first_day_of_month
while current_day <= now:
    days_of_month.append(current_day.strftime('%d/%m'))
    count = 0
    for entry in daily_leads:
        if entry['day'].date() == current_day.date():
            count = entry['count']
            break
    counts_per_day.append(count)
    current_day += timedelta(days=1)

print(f"\nDías generados: {len(days_of_month)}")
print(f"Días: {days_of_month}")
print(f"Conteos: {counts_per_day}")

# Verificar si hay datos
if any(counts_per_day):
    print("\n✅ Hay datos para mostrar en el gráfico.")
else:
    print("\n⚠️  No hay datos para el gráfico (todos los conteos son cero).")