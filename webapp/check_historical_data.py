"""
Script para verificar datos históricos en la base de datos de Meta Ads.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from meta_ads.models import MetaCampaignInsight
from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum
from datetime import datetime, timedelta

print("=== VERIFICACIÓN DE DATOS HISTÓRICOS META ADS ===\n")

# 1. Contar total de registros
total_insights = MetaCampaignInsight.objects.count()
print(f"Total de registros en MetaCampaignInsight: {total_insights}")

# 2. Obtener meses distintos con datos
months = MetaCampaignInsight.objects.annotate(
    month=TruncMonth('date')
).values('month').distinct().order_by('month')

print(f"\nMeses con datos en la base de datos ({months.count()} meses):")
for m in months:
    print(f"  - {m['month']}")

# 3. Conteo por mes
count_by_month = MetaCampaignInsight.objects.annotate(
    month=TruncMonth('date')
).values('month').annotate(
    count=Count('id'),
    total_spend=Sum('spend'),
    total_clicks=Sum('clicks')
).order_by('month')

print("\nDetalle por mes:")
for item in count_by_month:
    print(f"  - {item['month']}: {item['count']} registros, "
          f"S/ {item['total_spend'] or 0:.2f} gasto, "
          f"{item['total_clicks'] or 0} clics")

# 4. Verificar el rango de fechas
if total_insights > 0:
    min_date = MetaCampaignInsight.objects.aggregate(min_date=Min('date'))['min_date']
    max_date = MetaCampaignInsight.objects.aggregate(max_date=Max('date'))['max_date']
    print(f"\nRango de fechas en datos: {min_date} a {max_date}")
    
    # Calcular meses entre min y max
    if min_date and max_date:
        from dateutil.relativedelta import relativedelta
        months_diff = (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month)
        print(f"Meses entre primera y última fecha: {months_diff + 1}")
else:
    print("\nNo hay datos en la base de datos.")

# 5. Verificar qué está devolviendo _get_historical_kpis
print("\n=== PRUEBA DE _get_historical_kpis ===")
from meta_ads.views import MetaDashboardView
view = MetaDashboardView()
historical_data = view._get_historical_kpis(months=6)
print(f"Datos históricos devueltos (últimos 6 meses): {len(historical_data)} meses")
for item in historical_data:
    print(f"  - {item['month_name']}: S/ {item['total_spend']:.2f}, {item['total_clicks']} clics")