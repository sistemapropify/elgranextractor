#!/usr/bin/env python
"""
Script para probar la lógica de la vista dashboard exactamente como se ejecuta en el servidor.
"""
import os
import sys
import django
import json
from datetime import datetime, timedelta

# Configurar Django exactamente como en el servidor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from analisis_crm.models import Lead
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

def test_view_logic():
    print("=== TEST DE LÓGICA DE VISTA ===")
    
    # Copia exacta de la lógica de la vista
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"now: {now} (timezone: {now.tzinfo})")
    print(f"first_day_of_month: {first_day_of_month}")
    print(f"Diferencia en días: {(now - first_day_of_month).days}")
    
    # Verificar si el bucle se ejecutará
    current_day = first_day_of_month
    day_counter = 0
    while current_day <= now:
        day_counter += 1
        current_day += timedelta(days=1)
    
    print(f"El bucle se ejecutaría {day_counter} veces")
    
    # Ejecutar la consulta real
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"daily_leads count: {daily_leads.count()}")
    
    # Recrear las listas
    days_of_month = []
    counts_per_day = []
    
    current_day = first_day_of_month
    while current_day <= now:
        days_of_month.append(current_day.strftime('%d/%m'))
        count = 0
        current_date = current_day.date()
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']
                break
        counts_per_day.append(count)
        current_day += timedelta(days=1)
    
    print(f"days_of_month length: {len(days_of_month)}")
    print(f"counts_per_day length: {len(counts_per_day)}")
    
    if len(days_of_month) == 0:
        print("ERROR: days_of_month está vacío!")
        print(f"Condición del bucle: current_day={first_day_of_month}, now={now}")
        print(f"current_day <= now: {first_day_of_month <= now}")
        
        # Verificar si hay problema de timezone
        print(f"\n=== DEBUG TIMEZONE ===")
        print(f"now.date(): {now.date()}")
        print(f"first_day_of_month.date(): {first_day_of_month.date()}")
        print(f"now - first_day_of_month: {now - first_day_of_month}")
        
        # Forzar generación de días manualmente
        print("\nGenerando días manualmente para marzo 2026...")
        from datetime import date
        days_of_month = []
        counts_per_day = []
        for day in range(1, 24):  # hasta el día 23
            d = date(2026, 3, day)
            days_of_month.append(d.strftime('%d/%m'))
            counts_per_day.append(0)
        
        # Buscar datos reales
        for entry in daily_leads:
            print(f"Entry day: {entry['day']} (type: {type(entry['day'])})")
    
    # Convertir a JSON
    days_of_month_json = json.dumps(days_of_month)
    counts_per_day_json = json.dumps(counts_per_day)
    
    print(f"\n=== RESULTADOS ===")
    print(f"days_of_month: {days_of_month}")
    print(f"counts_per_day: {counts_per_day}")
    print(f"days_of_month_json: {days_of_month_json}")
    print(f"counts_per_day_json: {counts_per_day_json}")
    
    # Verificar si el JSON es válido
    try:
        parsed = json.loads(days_of_month_json)
        print(f"JSON parseado correctamente, longitud: {len(parsed)}")
    except Exception as e:
        print(f"ERROR parseando JSON: {e}")
    
    return days_of_month, counts_per_day

if __name__ == '__main__':
    test_view_logic()