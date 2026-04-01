"""
Test para verificar que _get_historical_kpis devuelve 6 meses completos.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from meta_ads.views import MetaDashboardView
from datetime import datetime

print("=== TEST DE _get_historical_kpis ACTUALIZADO ===\n")

view = MetaDashboardView()

# Probar con 6 meses
historical_data = view._get_historical_kpis(months=6)

print(f"Número de meses devueltos: {len(historical_data)}")
print("\nDetalle por mes:")
for item in historical_data:
    print(f"  - {item['month_name']}: S/ {item['total_spend']:.2f}, {item['total_clicks']} clics")

# Verificar que tenemos los últimos 6 meses
expected_months = 6
if len(historical_data) == expected_months:
    print(f"\n✅ CORRECTO: Se devuelven {expected_months} meses (incluyendo meses sin datos)")
else:
    print(f"\n❌ ERROR: Se esperaban {expected_months} meses pero se obtuvieron {len(historical_data)}")

# Verificar que incluye el mes actual
current_month = datetime.now().strftime('%B %Y')
current_in_data = any(current_month in item['month_name'] for item in historical_data)
if current_in_data:
    print(f"✅ El mes actual ({current_month}) está incluido")
else:
    print(f"❌ El mes actual ({current_month}) NO está incluido")