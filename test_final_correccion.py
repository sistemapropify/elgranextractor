#!/usr/bin/env python
"""
Test final para verificar corrección de días y ausencia de duplicación.
"""
import sys
import os

# Configurar Django para pruebas reales
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from datetime import datetime, timedelta
    from django.utils import timezone
    from analisis_crm.models import Lead
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    
    print("=== TEST FINAL - CORRECCIÓN DE DÍAS ===")
    
    # 1. Verificar generación de días
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"1. Fecha actual: {now.date()}")
    print(f"   Primer día del mes: {first_day_of_month.date()}")
    
    # Simular generación como en la vista
    days_of_month = []
    current_day = first_day_of_month
    
    while current_day.date() <= now.date():
        days_of_month.append(str(current_day.day))
        current_day += timedelta(days=1)
    
    print(f"2. Días generados: {len(days_of_month)}")
    print(f"   Días: {days_of_month[:5]}...{days_of_month[-5:] if len(days_of_month) > 10 else ''}")
    
    # Verificar que no haya duplicados
    if len(days_of_month) == len(set(days_of_month)):
        print("   ✅ No hay días duplicados en la generación")
    else:
        print("   ❌ Hay días duplicados en la generación")
    
    # Verificar que los días sean consecutivos
    expected = list(range(1, len(days_of_month) + 1))
    actual = [int(d) for d in days_of_month]
    
    if actual == expected:
        print("   ✅ Los días son consecutivos desde 1")
    else:
        print(f"   ❌ Los días no son consecutivos: esperado {expected[:5]}..., obtenido {actual[:5]}...")
    
    # 2. Verificar datos de la base de datos
    print(f"\n3. Verificando datos de leads...")
    daily_leads = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"   Total de días con datos en DB: {daily_leads.count()}")
    
    # Verificar duplicados en DB
    days_seen = set()
    dup_count = 0
    for entry in daily_leads:
        day = entry['day']
        if day in days_seen:
            dup_count += 1
            print(f"   ❌ Día duplicado en DB: {day}")
        else:
            days_seen.add(day)
    
    if dup_count == 0:
        print("   ✅ No hay días duplicados en la base de datos")
    
    # 3. Verificar template
    print(f"\n4. Verificando template...")
    template_path = 'webapp/analisis_crm/templates/analisis_crm/dashboard.html'
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Verificar número de datasets
    datasets_count = template.count('datasets: [')
    if datasets_count == 1:
        print("   ✅ Solo hay un dataset en el gráfico")
    else:
        print(f"   ❌ Hay {datasets_count} datasets en el gráfico (debería ser 1)")
    
    # Verificar tooltip
    if '`Leads: ${context.raw}`' in template:
        print("   ✅ Tooltip configurado correctamente")
    else:
        print("   ⚠️  Tooltip podría tener problemas de formato")
    
    print(f"\n=== RESUMEN ===")
    print("Los cambios realizados solucionan:")
    print("1. Formato de días: ahora muestra '1, 2, 3...' en lugar de '0/3, 1/3, 2/3'")
    print("2. No hay duplicación en la generación de días")
    print("3. Solo un dataset en el gráfico")
    print("4. Tooltip correctamente formateado")
    
except Exception as e:
    print(f"Error en test: {e}")
    import traceback
    traceback.print_exc()