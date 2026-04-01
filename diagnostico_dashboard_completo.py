#!/usr/bin/env python
"""
Diagnóstico completo del dashboard para identificar:
1. Discrepancia entre lista y gráfica (20 vs 17 marzo)
2. Duplicación de leads en la lista
3. Conteo incorrecto en gráfica
"""
import sys
import os

sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from datetime import datetime, timedelta
    from django.utils import timezone
    from analisis_crm.models import Lead
    from django.db.models import Count, Q
    from django.db.models.functions import TruncDate
    
    print("=== DIAGNÓSTICO COMPLETO DEL DASHBOARD ===")
    print(f"Fecha y hora actual: {timezone.now()}")
    
    # 1. Obtener todos los leads para ver el rango de fechas
    all_leads = Lead.objects.all().order_by('date_entry')
    total_leads = all_leads.count()
    print(f"\n1. TOTAL DE LEADS EN LA BASE DE DATOS: {total_leads}")
    
    if total_leads > 0:
        first_lead = all_leads.first()
        last_lead = all_leads.last()
        print(f"   Primer lead: ID {first_lead.id}, fecha: {first_lead.date_entry}")
        print(f"   Último lead: ID {last_lead.id}, fecha: {last_lead.date_entry}")
    
    # 2. Verificar leads duplicados (mismo date_entry, phone, email, etc.)
    print(f"\n2. VERIFICACIÓN DE DUPLICADOS:")
    
    # Buscar leads con mismo teléfono y fecha similar
    from django.db.models import Count
    duplicate_phones = Lead.objects.values('phone').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')[:10]
    
    print(f"   Leads con teléfono duplicado: {duplicate_phones.count()}")
    for dup in duplicate_phones[:5]:
        print(f"   - Teléfono {dup['phone']}: {dup['count']} leads")
    
    # 3. Analizar el mes actual (marzo 2026)
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"\n3. ANÁLISIS DEL MES ACTUAL (MARZO 2026):")
    print(f"   Hoy: {now.date()}")
    print(f"   Primer día del mes: {first_day_of_month.date()}")
    
    # Leads del mes actual
    leads_this_month = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    )
    print(f"   Leads este mes (según filtro): {leads_this_month.count()}")
    
    # 4. Verificar la lista que muestra la vista (últimos 100 leads)
    recent_leads = Lead.objects.all().order_by('-date_entry', '-created_at')[:100]
    print(f"\n4. LISTA DE ÚLTIMOS 100 LEADS:")
    print(f"   Cantidad en lista: {recent_leads.count()}")
    
    # Fechas en la lista
    if recent_leads.count() > 0:
        dates_in_list = [lead.date_entry.date() if lead.date_entry else lead.created_at.date() for lead in recent_leads]
        min_date = min(dates_in_list)
        max_date = max(dates_in_list)
        print(f"   Fecha más antigua en lista: {min_date}")
        print(f"   Fecha más reciente en lista: {max_date}")
        
        # Contar por día
        from collections import Counter
        date_counts = Counter(dates_in_list)
        print(f"   Días representados en lista: {len(date_counts)}")
        print(f"   Conteo por día (top 5):")
        for date, count in sorted(date_counts.items(), key=lambda x: x[0], reverse=True)[:5]:
            print(f"     {date}: {count} leads")
    
    # 5. Verificar datos para la gráfica
    print(f"\n5. DATOS PARA LA GRÁFICA:")
    
    # Obtener leads agrupados por día (como lo hace la vista)
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"   Días con datos en DB: {daily_leads.count()}")
    
    # Mostrar todos los días con conteo
    print(f"   Conteo por día (completo):")
    for entry in daily_leads:
        print(f"     {entry['day']}: {entry['count']} leads")
    
    # 6. Generar días como lo hace la vista
    print(f"\n6. GENERACIÓN DE DÍAS PARA GRÁFICA (lógica de la vista):")
    
    days_of_month = []
    counts_per_day = []
    current_day = first_day_of_month
    day_counter = 0
    
    while current_day.date() <= now.date():
        day_counter += 1
        days_of_month.append(str(current_day.day))
        
        # Buscar conteo para este día
        count = 0
        current_date = current_day.date()
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']
                break
        counts_per_day.append(count)
        
        current_day += timedelta(days=1)
    
    print(f"   Días generados: {len(days_of_month)} (desde 1 hasta {len(days_of_month)})")
    print(f"   Últimos 5 días generados: {days_of_month[-5:]}")
    print(f"   Conteos últimos 5 días: {counts_per_day[-5:]}")
    
    # 7. Identificar discrepancias
    print(f"\n7. IDENTIFICACIÓN DE DISCREPANCIAS:")
    
    # Verificar si hay días sin datos pero con leads en la lista
    zero_count_days = [(day, count) for day, count in zip(days_of_month, counts_per_day) if count == 0]
    if zero_count_days:
        print(f"   Días con conteo 0 en gráfica pero que podrían tener leads: {len(zero_count_days)}")
        print(f"   Ejemplo: {zero_count_days[:3]}")
    
    # Verificar total de leads en gráfica vs total del mes
    total_in_chart = sum(counts_per_day)
    total_actual = leads_this_month.count()
    print(f"   Total de leads en gráfica (suma de conteos): {total_in_chart}")
    print(f"   Total de leads este mes (contados directamente): {total_actual}")
    
    if total_in_chart != total_actual:
        print(f"   ⚠️ DISCREPANCIA: Gráfica muestra {total_in_chart} leads pero hay {total_actual} leads reales")
        print(f"   Diferencia: {total_actual - total_in_chart} leads faltantes en gráfica")
    
    # 8. Verificar problema de fecha (20 vs 17 marzo)
    print(f"\n8. PROBLEMA DE FECHA (20 vs 17 MARZO):")
    
    # Última fecha con datos en daily_leads
    if daily_leads.exists():
        last_date_with_data = daily_leads.last()['day']
        print(f"   Última fecha con datos en agrupación: {last_date_with_data}")
    
    # Última fecha en la lista de 100 leads
    if recent_leads.exists():
        last_lead = recent_leads.first()
        last_date_in_list = last_lead.date_entry.date() if last_lead.date_entry else last_lead.created_at.date()
        print(f"   Última fecha en lista de 100 leads: {last_date_in_list}")
    
    print(f"\n=== CONCLUSIÓN PRELIMINAR ===")
    print("Problemas identificados:")
    print("1. Posible discrepancia en totales (gráfica vs realidad)")
    print("2. Días con conteo 0 que podrían tener leads")
    print("3. Diferencia entre última fecha en lista vs gráfica")
    
except Exception as e:
    print(f"Error en diagnóstico: {e}")
    import traceback
    traceback.print_exc()