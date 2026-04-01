#!/usr/bin/env python
"""
Verificar que los datos coincidan entre lista y gráfica.
"""
import sys
import os

sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from analisis_crm.models import Lead
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    print("=== VERIFICACIÓN DE COINCIDENCIA LISTA vs GRÁFICA ===")
    
    # 1. Obtener datos como lo hace la vista dashboard
    # Lista de últimos 100 leads
    recent_leads = Lead.objects.all().order_by('-date_entry', '-created_at')[:100]
    
    print(f"1. LISTA DE ÚLTIMOS 100 LEADS:")
    print(f"   Total en lista: {recent_leads.count()}")
    
    # Fechas en la lista
    list_dates = []
    for lead in recent_leads:
        if lead.date_entry:
            list_dates.append(lead.date_entry.date())
    
    if list_dates:
        min_list_date = min(list_dates)
        max_list_date = max(list_dates)
        print(f"   Rango de fechas en lista: {min_list_date} a {max_list_date}")
        print(f"   Días cubiertos: {(max_list_date - min_list_date).days + 1} días")
    
    # 2. Obtener datos de gráfica (como lo hace la vista)
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"\n2. DATOS DE GRÁFICA:")
    print(f"   Total de días con datos: {daily_leads.count()}")
    
    if daily_leads:
        first_graph_date = daily_leads[0]['day']
        last_graph_date = daily_leads[daily_leads.count()-1]['day']
        print(f"   Rango de fechas en gráfica: {first_graph_date} a {last_graph_date}")
    
    # 3. Comparar conteos por día
    print(f"\n3. COMPARACIÓN POR DÍA (últimos 5 días):")
    
    # Obtener últimos 5 días con datos en la lista
    unique_dates = sorted(set(list_dates), reverse=True)[:5]
    
    for date in unique_dates:
        # Conteo en lista (últimos 100 leads)
        count_in_list = sum(1 for d in list_dates if d == date)
        
        # Conteo en gráfica (todos los leads de ese día)
        count_in_graph = Lead.objects.filter(date_entry__date=date).count()
        
        # Conteo de leads únicos por teléfono
        unique_phones = Lead.objects.filter(
            date_entry__date=date,
            phone__isnull=False
        ).values('phone').distinct().count()
        
        print(f"   {date}:")
        print(f"     - En lista (últimos 100): {count_in_list}")
        print(f"     - En gráfica (total día): {count_in_graph}")
        print(f"     - Únicos por teléfono: {unique_phones}")
        
        if count_in_list != count_in_graph:
            print(f"     ⚠️ DISCREPANCIA: Lista={count_in_list} vs Gráfica={count_in_graph}")
        
        if count_in_graph > unique_phones:
            print(f"     ⚠️ DUPLICACIÓN: {count_in_graph - unique_phones} duplicados en datos de gráfica")
    
    # 4. Verificar problema específico del usuario (gráfica muestra hasta 17 marzo)
    print(f"\n4. INVESTIGACIÓN PROBLEMA USUARIO:")
    print(f"   Usuario reporta: 'la gráfica da hasta el 17 de marzo'")
    print(f"   Realidad: La gráfica debería mostrar hasta el {last_graph_date if daily_leads else 'N/A'}")
    
    # Verificar si hay datos después del 17 de marzo
    march_17 = datetime(2026, 3, 17).date()
    march_18 = datetime(2026, 3, 18).date()
    march_19 = datetime(2026, 3, 19).date()
    march_20 = datetime(2026, 3, 20).date()
    
    for date in [march_17, march_18, march_19, march_20]:
        count = Lead.objects.filter(date_entry__date=date).count()
        print(f"   {date}: {count} leads")
    
    # 5. Verificar datos pasados al template
    print(f"\n5. SIMULACIÓN DE DATOS PASADOS AL TEMPLATE:")
    
    # Simular la lógica de la vista
    days_of_month = []
    counts_per_day = []
    
    current_day = first_day_of_month
    while current_day.date() <= now.date():
        days_of_month.append(str(current_day.day))
        
        count = 0
        current_date = current_day.date()
        for entry in daily_leads:
            if entry['day'] == current_date:
                count = entry['count']
                break
        counts_per_day.append(count)
        
        current_day += timedelta(days=1)
    
    print(f"   Días generados: {len(days_of_month)} (del 1 al {days_of_month[-1] if days_of_month else 'N/A'})")
    print(f"   Últimos 5 días de gráfica:")
    
    for i in range(max(0, len(days_of_month)-5), len(days_of_month)):
        day_num = days_of_month[i]
        count = counts_per_day[i]
        print(f"     Día {day_num}: {count} leads")
    
    # 6. Recomendaciones
    print(f"\n6. RECOMENDACIONES:")
    
    # Verificar si hay problema con JavaScript
    print(f"   a) Verificar que el JavaScript en dashboard.html reciba correctamente:")
    print(f"      - days_of_month: {days_of_month[-5:] if len(days_of_month) >= 5 else days_of_month}")
    print(f"      - counts_per_day: {counts_per_day[-5:] if len(counts_per_day) >= 5 else counts_per_day}")
    
    # Verificar problema de duplicación
    duplicate_count = sum(1 for count in counts_per_day if count > 0)
    print(f"   b) Problema de duplicación en lista: {recent_leads.count()} leads, pero muchos duplicados")
    print(f"      - Solución: Mostrar leads únicos en la lista")
    
    # Verificar coincidencia de datos
    print(f"   c) Coincidencia lista/gráfica: La lista muestra últimos 100 leads,")
    print(f"      la gráfica muestra todos los leads del mes")
    print(f"      - Esto puede causar percepción de discrepancia")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()