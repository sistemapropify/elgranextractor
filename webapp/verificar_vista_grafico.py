#!/usr/bin/env python
"""
Verificación exacta de lo que la vista está calculando para el gráfico
"""
import os
import sys
import django
import json
import calendar
from datetime import datetime, timedelta

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from analisis_crm.models import Lead
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

def simular_vista_dashboard():
    """Simular exactamente lo que hace la función dashboard()"""
    print("=== SIMULACIÓN DE LA VISTA DASHBOARD ===")
    
    # Copiar lógica de la vista
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"now: {now}")
    print(f"first_day_of_month: {first_day_of_month}")
    
    # Obtener leads agrupados por día (date_entry) - EXACTAMENTE como la vista
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"\nResultado de daily_leads (mismo filtro que vista):")
    print(f"Número de días con datos: {daily_leads.count()}")
    
    # Mostrar todos los días con datos
    for entry in daily_leads:
        print(f"  {entry['day']}: {entry['count']}")
    
    # Buscar específicamente el 5 de marzo
    fecha_5_marzo = datetime(2026, 3, 5).date()
    count_5_marzo_vista = 0
    for entry in daily_leads:
        if entry['day'] == fecha_5_marzo:
            count_5_marzo_vista = entry['count']
            break
    
    print(f"\nConteo para 5/3/2026 en daily_leads: {count_5_marzo_vista}")
    
    # Ahora simular la generación de días del mes
    year = now.year
    month = now.month
    last_day_of_month = calendar.monthrange(year, month)[1]
    last_day_datetime = now.replace(day=last_day_of_month, hour=23, minute=59, second=59)
    
    print(f"\nGenerando días del mes:")
    print(f"Mes: {month}/{year}")
    print(f"Último día: {last_day_of_month}")
    print(f"last_day_datetime: {last_day_datetime}")
    
    days_of_month = []
    counts_per_day = []
    
    current_day = first_day_of_month
    day_counter = 0
    
    print(f"\nBucle while current_day <= last_day_datetime:")
    while current_day <= last_day_datetime:
        day_counter += 1
        day_str = current_day.strftime('%d/%m')
        days_of_month.append(day_str)
        
        # Buscar conteo para este día (igual que la vista)
        count = 0
        current_date = current_day.date()
        
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']
                break
        
        counts_per_day.append(count)
        
        # Mostrar para el 5 de marzo
        if current_date == fecha_5_marzo:
            print(f"  Día {day_counter}: {day_str} (5/3/2026) -> count encontrado: {count}")
            print(f"    current_date: {current_date}")
            print(f"    Búsqueda en daily_leads:")
            for entry in daily_leads:
                if entry['day'] == current_date:
                    print(f"      Encontrado: {entry['day']} = {entry['count']}")
        
        current_day += timedelta(days=1)
    
    print(f"\nResumen final:")
    print(f"Días generados: {len(days_of_month)}")
    print(f"Conteos generados: {len(counts_per_day)}")
    
    # Encontrar índice del 5 de marzo
    try:
        idx = days_of_month.index('05/03')
        print(f"\nÍndice del 5/3 en days_of_month: {idx}")
        print(f"Valor en counts_per_day[{idx}]: {counts_per_day[idx]}")
        print(f"Día correspondiente: {days_of_month[idx]}")
    except ValueError:
        print("ERROR: '05/03' no encontrado en days_of_month")
        print(f"days_of_month: {days_of_month}")
    
    # Verificar JSON
    days_json = json.dumps(days_of_month)
    counts_json = json.dumps(counts_per_day)
    
    print(f"\nJSON generado:")
    print(f"days_of_month_json: {days_json[:100]}...")
    print(f"counts_per_day_json: {counts_json[:100]}...")
    
    # Buscar el valor para el 5 de marzo en el JSON
    import re
    # Encontrar el índice del 5/3 en el array JSON
    pattern = r'"05/03"'
    match = re.search(pattern, days_json)
    if match:
        # Encontrar la posición
        start_pos = match.start()
        # Contar comas antes de esta posición para obtener el índice
        substring = days_json[:start_pos]
        index = substring.count(',')
        print(f"\nEn JSON: '05/03' está en índice {index}")
        
        # Extraer el valor correspondiente de counts_json
        counts_list = json.loads(counts_json)
        if index < len(counts_list):
            print(f"Valor en counts_json[{index}]: {counts_list[index]}")
    
    return count_5_marzo_vista, counts_per_day

def verificar_discrepancia():
    """Verificar por qué hay discrepancia entre 12 y 10"""
    print("\n=== VERIFICACIÓN DE DISCREPANCIA ===")
    
    # Contar directamente leads del 5 de marzo
    fecha_5_marzo = datetime(2026, 3, 5).date()
    leads_directos = Lead.objects.filter(date_entry__date=fecha_5_marzo)
    count_directo = leads_directos.count()
    
    print(f"Leads del 5/3/2026 (contado directamente): {count_directo}")
    
    # Listar todos los leads del 5 de marzo para verificar
    print(f"\nLista de leads del 5/3/2026:")
    for i, lead in enumerate(leads_directos[:15]):  # Mostrar primeros 15
        print(f"  {i+1}. ID: {lead.id}, date_entry: {lead.date_entry}")
    
    # Verificar si algún lead tiene date_entry nulo o diferente
    print(f"\nVerificando problemas potenciales:")
    
    # 1. Leads con date_entry nulo
    null_count = Lead.objects.filter(date_entry__isnull=True).count()
    print(f"1. Leads con date_entry NULL: {null_count}")
    
    # 2. Leads con date_entry fuera del rango del filtro
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    leads_fuera_rango = Lead.objects.filter(
        date_entry__date=fecha_5_marzo
    ).exclude(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    )
    
    fuera_rango_count = leads_fuera_rango.count()
    print(f"2. Leads del 5/3 fuera del rango de filtro (>= {first_day_of_month} y <= {now}): {fuera_rango_count}")
    
    if fuera_rango_count > 0:
        print(f"   Estos leads no serían incluidos en daily_leads:")
        for lead in leads_fuera_rango:
            print(f"     ID: {lead.id}, date_entry: {lead.date_entry}")
    
    # 3. Verificar timezone issues
    print(f"\n3. Verificación de timezone:")
    print(f"   TIME_ZONE configurado: UTC")
    print(f"   now (con timezone): {now}")
    print(f"   first_day_of_month (con timezone): {first_day_of_month}")
    
    # Ejemplo de un lead
    lead_ejemplo = leads_directos.first()
    if lead_ejemplo:
        print(f"   Ejemplo lead: date_entry={lead_ejemplo.date_entry}, tzinfo={lead_ejemplo.date_entry.tzinfo}")
        
        # Verificar si está dentro del rango
        in_range = first_day_of_month <= lead_ejemplo.date_entry <= now
        print(f"   ¿Está dentro del rango? {in_range}")
        if not in_range:
            print(f"   Problema: lead fuera del rango de filtro")

def main():
    print("VERIFICACIÓN DE GRÁFICO - ¿POR QUÉ MUESTRA 10 EN LUGAR DE 12?")
    print("=" * 70)
    
    # Simular la vista
    count_vista, counts_list = simular_vista_dashboard()
    
    # Verificar discrepancia
    verificar_discrepancia()
    
    print("\n" + "=" * 70)
    print("CONCLUSIÓN:")
    
    # Contar directamente
    fecha_5_marzo = datetime(2026, 3, 5).date()
    count_directo = Lead.objects.filter(date_entry__date=fecha_5_marzo).count()
    
    print(f"- Leads reales del 5/3/2026: {count_directo}")
    print(f"- Leads que la vista encuentra: {count_vista}")
    
    if count_directo != count_vista:
        print(f"¡PROBLEMA ENCONTRADO! La vista está perdiendo {count_directo - count_vista} leads")
        print("Posibles causas:")
        print("1. Filtro de rango incorrecto (date_entry__gte y date_entry__lte)")
        print("2. Problema de timezone en la comparación")
        print("3. Leads con date_entry justo en el límite del rango")
    else:
        print("✓ La vista encuentra todos los leads correctamente")
        
        # Verificar el valor en counts_per_day
        try:
            # Encontrar índice del 5/3
            now = timezone.now()
            first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fecha_5 = datetime(2026, 3, 5).date()
            
            # Calcular índice (día 5 = índice 4 si empezamos desde 1)
            delta = fecha_5 - first_day.date()
            idx = delta.days
            
            if 0 <= idx < len(counts_list):
                print(f"- Valor en counts_per_day[{idx}] (para 5/3): {counts_list[idx]}")
                if counts_list[idx] != count_directo:
                    print(f"  ¡DISCREPANCIA! El gráfico mostraría {counts_list[idx]} en lugar de {count_directo}")
                else:
                    print(f"  ✓ Correcto, el gráfico mostraría {counts_list[idx]}")
        except Exception as e:
            print(f"Error calculando índice: {e}")

if __name__ == '__main__':
    main()