#!/usr/bin/env python
"""
Script para probar la lógica de datos del dashboard de leads.
"""
import os
import sys
import django
import json
from datetime import datetime, timedelta

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from analisis_crm.models import Lead
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

def test_dashboard_data():
    print("=== PRUEBA DE DATOS DEL DASHBOARD ===")
    
    # Obtener todos los leads (podría ser muchos, considerar paginación)
    leads = Lead.objects.all().order_by('-date_entry', '-created_at')[:5]
    print(f"Últimos 5 leads: {list(leads.values('id', 'full_name', 'date_entry'))}")
    
    # Estadísticas básicas
    total_leads = Lead.objects.count()
    active_leads = Lead.objects.filter(is_active=True).count()
    leads_last_7_days = Lead.objects.filter(
        date_entry__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    print(f"Total leads: {total_leads}")
    print(f"Leads activos: {active_leads}")
    print(f"Leads últimos 7 días: {leads_last_7_days}")
    
    # Evolución de leads por día del mes actual
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"\n=== DATOS PARA GRÁFICO ===")
    print(f"Mes actual: {now.month}/{now.year}")
    print(f"Primer día del mes: {first_day_of_month}")
    print(f"Hoy: {now}")
    
    # Obtener leads agrupados por día (date_entry)
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"\nResultados de daily_leads (raw):")
    for entry in daily_leads:
        print(f"  {entry['day']}: {entry['count']} leads")
    
    print(f"\nTotal de días con datos: {daily_leads.count()}")
    
    # Crear estructura para el gráfico: lista de días y conteos
    days_of_month = []
    counts_per_day = []
    
    # Generar todos los días del mes actual
    current_day = first_day_of_month
    while current_day <= now:
        days_of_month.append(current_day.strftime('%d/%m'))
        # Buscar conteo para este día
        count = 0
        current_date = current_day.date()  # Convertir datetime a date
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']
                break
        counts_per_day.append(count)
        current_day += timedelta(days=1)
    
    print(f"\nDías generados: {len(days_of_month)} días")
    print(f"Días: {days_of_month}")
    print(f"Conteos: {counts_per_day}")
    
    # Verificar si las listas están vacías
    if not days_of_month:
        print("ERROR: days_of_month está vacío")
    if not counts_per_day:
        print("ERROR: counts_per_day está vacío")
    
    # Convertir a JSON para uso en JavaScript
    days_of_month_json = json.dumps(days_of_month)
    counts_per_day_json = json.dumps(counts_per_day)
    
    print(f"\nJSON días: {days_of_month_json}")
    print(f"JSON conteos: {counts_per_day_json}")
    
    # Verificar si hay datos reales
    total_counts = sum(counts_per_day)
    print(f"\nTotal de leads en el mes (suma de conteos): {total_counts}")
    
    # Verificar si hay leads en la base de datos
    leads_in_month = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).count()
    print(f"Leads en el mes (directo de BD): {leads_in_month}")
    
    return {
        'days_of_month': days_of_month,
        'counts_per_day': counts_per_day,
        'days_of_month_json': days_of_month_json,
        'counts_per_day_json': counts_per_day_json,
    }

if __name__ == '__main__':
    test_dashboard_data()