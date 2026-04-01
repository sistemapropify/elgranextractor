#!/usr/bin/env python
"""
Script para diagnosticar el problema de días que no coinciden en la gráfica.
"""
import os
import sys
import django
from datetime import datetime, timedelta
import calendar
import json

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.utils import timezone
from analisis_crm.models import Lead

def diagnosticar_problema_dias():
    print("=== DIAGNÓSTICO DE PROBLEMA DE DÍAS ===")
    print(f"Fecha actual del sistema: {datetime.now()}")
    print(f"Fecha actual con timezone: {timezone.now()}")
    print(f"Zona horaria: {timezone.get_current_timezone()}")
    
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"\n=== INFORMACIÓN DEL MES ACTUAL ===")
    print(f"now: {now}")
    print(f"first_day_of_month: {first_day_of_month}")
    print(f"Diferencia en días: {(now - first_day_of_month).days}")
    
    # Obtener leads agrupados por día
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"\n=== LEADS POR DÍA (DATABASE) ===")
    print(f"Total de registros diarios: {daily_leads.count()}")
    
    for entry in daily_leads:
        print(f"  {entry['day']}: {entry['count']}")
    
    # Calcular último día del mes actual
    year = now.year
    month = now.month
    last_day_of_month = calendar.monthrange(year, month)[1]
    last_day_datetime = now.replace(day=last_day_of_month, hour=23, minute=59, second=59)
    
    print(f"\n=== GENERACIÓN DE DÍAS PARA GRÁFICA ===")
    print(f"Mes actual: {month}/{year}")
    print(f"Último día del mes: {last_day_of_month}")
    print(f"last_day_datetime: {last_day_datetime}")
    
    # Generar días del mes
    days_of_month = []
    counts_per_day = []
    
    current_day = first_day_of_month
    day_counter = 0
    
    while current_day <= last_day_datetime:
        day_counter += 1
        day_str = current_day.strftime('%d/%m')
        days_of_month.append(day_str)
        
        # Buscar conteo para este día
        count = 0
        current_date = current_day.date()
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']
                break
        counts_per_day.append(count)
        
        print(f"Día {day_counter}: {day_str} -> {count} leads")
        current_day += timedelta(days=1)
    
    print(f"\n=== RESUMEN ===")
    print(f"Total de días generados: {day_counter}")
    print(f"Días: {days_of_month}")
    print(f"Conteos: {counts_per_day}")
    
    # Verificar si hay días faltantes o duplicados
    if len(set(days_of_month)) != len(days_of_month):
        print("\n⚠️ ADVERTENCIA: Hay días duplicados en la lista!")
    
    # Verificar formato de fechas
    print(f"\n=== VERIFICACIÓN DE FORMATO ===")
    print(f"Formato usado: 'dd/mm'")
    print(f"Ejemplo: {days_of_month[0] if days_of_month else 'N/A'}")
    
    return days_of_month, counts_per_day

if __name__ == "__main__":
    # Necesitamos importar las funciones de Django
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    
    try:
        diagnosticar_problema_dias()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()