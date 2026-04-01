"""
Script para sincronizar datos históricos de Meta Ads (últimos 6 meses).
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from meta_ads.services import MetaAdsSyncService
from datetime import datetime

print("=== SINCRONIZACIÓN HISTÓRICA DE META ADS ===\n")

try:
    # Crear instancia del servicio
    service = MetaAdsSyncService()
    
    print("1. Sincronizando campañas...")
    campaigns_created, campaigns_updated = service.sync_campaigns()
    print(f"   ✅ Campañas: {campaigns_created} creadas, {campaigns_updated} actualizadas")
    
    print("\n2. Sincronizando insights históricos (últimos 180 días)...")
    insights_created, insights_updated = service.sync_insights(days=180)
    print(f"   ✅ Insights: {insights_created} creados, {insights_updated} actualizados")
    
    print("\n3. Verificando datos...")
    from meta_ads.models import MetaCampaignInsight
    from django.db.models import Min, Max, Count
    
    stats = MetaCampaignInsight.objects.aggregate(
        min_date=Min('date'),
        max_date=Max('date'),
        count=Count('*')
    )
    
    print(f"   📊 Rango de fechas: {stats['min_date']} a {stats['max_date']}")
    print(f"   📊 Total de registros: {stats['count']}")
    
    # Verificar meses con datos
    from django.db.models.functions import TruncMonth
    from django.db.models import Sum
    
    monthly_data = MetaCampaignInsight.objects.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        total_spend=Sum('spend'),
        count=Count('*')
    ).order_by('-month')
    
    print(f"\n4. Meses con datos:")
    for item in monthly_data[:12]:  # Últimos 12 meses
        month_name = item['month'].strftime('%B %Y')
        spend = item['total_spend'] or 0
        count = item['count']
        print(f"   - {month_name}: S/ {spend:.2f} ({count} registros)")
    
    print("\n✅ Sincronización histórica completada exitosamente!")
    
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("   Asegúrate de tener instalado 'facebook-business'")
except Exception as e:
    print(f"❌ Error durante la sincronización: {e}")
    import traceback
    traceback.print_exc()