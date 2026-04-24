#!/usr/bin/env python
"""
Script para verificar datos de Meta Ads en la base de datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from meta_ads.models import MetaCampaign, MetaCampaignInsight
from django.utils import timezone

def main():
    print("=== Verificación de datos Meta Ads ===")
    
    # Contar datos totales
    total_campaigns = MetaCampaign.objects.count()
    total_insights = MetaCampaignInsight.objects.count()
    
    print(f"Campañas totales: {total_campaigns}")
    print(f"Insights totales: {total_insights}")
    
    # Verificar datos de hoy
    today = timezone.now().date()
    print(f"\nFecha de hoy: {today}")
    
    insights_hoy = MetaCampaignInsight.objects.filter(date=today)
    count_hoy = insights_hoy.count()
    
    print(f"Insights para hoy: {count_hoy}")
    
    if count_hoy > 0:
        total_spend_hoy = sum(i.spend for i in insights_hoy)
        total_clicks_hoy = sum(i.clicks for i in insights_hoy)
        print(f"Gasto total hoy: S/. {total_spend_hoy:.2f}")
        print(f"Clics totales hoy: {total_clicks_hoy}")
    else:
        print("No hay datos para hoy")
        
        # Mostrar las fechas más recientes disponibles
        latest_insights = MetaCampaignInsight.objects.order_by('-date')[:5]
        print("\nFechas más recientes disponibles:")
        for insight in latest_insights:
            print(f"  - {insight.date}: S/. {insight.spend:.2f}, {insight.clicks} clics")
    
    # Verificar si hay campañas activas
    active_campaigns = MetaCampaign.objects.filter(status=MetaCampaign.STATUS_ACTIVE)
    print(f"\nCampañas activas: {active_campaigns.count()}")
    
    if active_campaigns.exists():
        print("Campañas activas encontradas:")
        for campaign in active_campaigns[:5]:  # Mostrar solo las primeras 5
            print(f"  - {campaign.name} (ID: {campaign.campaign_id})")

if __name__ == '__main__':
    main()