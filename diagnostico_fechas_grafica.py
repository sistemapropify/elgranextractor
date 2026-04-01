#!/usr/bin/env python
"""
Diagnóstico del problema de fechas en la gráfica.
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
    
    print("=== DIAGNÓSTICO DE FECHAS EN GRÁFICA ===")
    
    # 1. Obtener fechas extremas de los leads
    latest_lead = Lead.objects.filter(date_entry__isnull=False).order_by('-date_entry').first()
    earliest_lead = Lead.objects.filter(date_entry__isnull=False).order_by('date_entry').first()
    
    print(f"1. FECHAS EXTREMAS DE LEADS:")
    print(f"   Lead más reciente: {latest_lead.date_entry if latest_lead else 'N/A'}")
    print(f"   Lead más antiguo: {earliest_lead.date_entry if earliest_lead else 'N/A'}")
    
    # 2. Verificar leads del mes actual (marzo 2026)
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"\n2. MES ACTUAL (marzo 2026):")
    print(f"   Fecha actual: {now}")
    print(f"   Primer día del mes: {first_day_of_month}")
    
    # 3. Obtener leads agrupados por día (como lo hace la vista)
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"\n3. DATOS DE GRÁFICA ACTUAL:")
    print(f"   Total de días con datos: {daily_leads.count()}")
    
    # Mostrar todos los días con datos
    days_with_data = []
    for entry in daily_leads:
        day_str = entry['day'].strftime('%Y-%m-%d')
        days_with_data.append(day_str)
        print(f"   {day_str}: {entry['count']} leads")
    
    # 4. Verificar el último día con datos
    if days_with_data:
        last_day_with_data = days_with_data[-1]
        print(f"\n4. ÚLTIMO DÍA CON DATOS: {last_day_with_data}")
        
        # Convertir a datetime para comparar
        last_date = datetime.strptime(last_day_with_data, '%Y-%m-%d').date()
        today_date = now.date()
        
        print(f"   Hoy: {today_date}")
        print(f"   Diferencia en días: {(today_date - last_date).days}")
        
        if (today_date - last_date).days > 0:
            print(f"   ⚠️ La gráfica muestra hasta {last_date}, pero hoy es {today_date}")
    
    # 5. Verificar si hay leads después del último día mostrado
    if latest_lead and latest_lead.date_entry:
        latest_date = latest_lead.date_entry.date()
        print(f"\n5. LEAD MÁS RECIENTE EN BASE DE DATOS:")
        print(f"   Fecha: {latest_date}")
        
        if days_with_data:
            last_graph_date = datetime.strptime(days_with_data[-1], '%Y-%m-%d').date()
            if latest_date > last_graph_date:
                print(f"   ⚠️ DISCREPANCIA: Hay leads del {latest_date} pero la gráfica solo muestra hasta {last_graph_date}")
                print(f"   Posible causa: El filtro date_entry__lte=now excluye leads con fecha futura")
            elif latest_date < last_graph_date:
                print(f"   ⚠️ DISCREPANCIA: La gráfica muestra hasta {last_graph_date} pero el lead más reciente es del {latest_date}")
    
    # 6. Verificar leads por día para marzo
    print(f"\n6. RESUMEN POR DÍA DE MARZO 2026:")
    
    # Generar todos los días de marzo
    import calendar
    year = 2026
    month = 3
    last_day = calendar.monthrange(year, month)[1]
    
    for day in range(1, last_day + 1):
        target_date = datetime(year, month, day).date()
        count = Lead.objects.filter(
            date_entry__date=target_date
        ).count()
        
        if count > 0:
            print(f"   {day:02d}/03: {count} leads")
    
    # 7. Verificar problema de duplicación en conteos
    print(f"\n7. VERIFICACIÓN DE DUPLICACIÓN EN CONTEO DIARIO:")
    
    # Obtener leads únicos por teléfono por día
    from django.db.models import Count, Q
    
    for day in range(1, min(24, last_day + 1)):  # Solo primeros 23 días
        target_date = datetime(year, month, day).date()
        
        # Conteo normal (como lo hace la vista)
        total_count = Lead.objects.filter(date_entry__date=target_date).count()
        
        # Conteo de leads únicos por teléfono
        unique_phones = Lead.objects.filter(
            date_entry__date=target_date,
            phone__isnull=False
        ).values('phone').distinct().count()
        
        # Conteo de leads únicos por email
        unique_emails = Lead.objects.filter(
            date_entry__date=target_date,
            email__isnull=False
        ).values('email').distinct().count()
        
        if total_count > 0:
            print(f"   {day:02d}/03: Total={total_count}, Únicos(tel)={unique_phones}, Únicos(email)={unique_emails}")
            if total_count > unique_phones:
                print(f"     ⚠️ {total_count - unique_phones} duplicados por teléfono")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()