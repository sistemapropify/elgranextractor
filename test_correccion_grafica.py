#!/usr/bin/env python
"""
Test para verificar la corrección de la gráfica con leads únicos.
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
    
    print("=== TEST CORRECCIÓN GRÁFICA CON LEADS ÚNICOS ===")
    
    # 1. Lógica actual (con duplicados)
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print("1. LÓGICA ACTUAL (con duplicados):")
    daily_leads_current = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"   Total días: {daily_leads_current.count()}")
    total_leads_current = sum(entry['count'] for entry in daily_leads_current)
    print(f"   Total leads (con duplicados): {total_leads_current}")
    
    # 2. Lógica propuesta (leads únicos por teléfono)
    print("\n2. LÓGICA PROPUESTA (leads únicos por teléfono):")
    
    # Para cada día, contar leads únicos por teléfono
    # Necesitamos una consulta más compleja
    from django.db.models import Subquery, OuterRef
    
    # Primero, obtener todos los días del mes con leads
    all_days = Lead.objects.filter(
        date_entry__gte=first_day_of_month,
        date_entry__lte=now
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').distinct().order_by('day')
    
    print(f"   Días con leads: {all_days.count()}")
    
    # Para cada día, contar leads únicos
    daily_unique_counts = []
    for day_entry in all_days:
        day = day_entry['day']
        
        # Conteo actual (con duplicados)
        total_count = Lead.objects.filter(date_entry__date=day).count()
        
        # Conteo de leads únicos por teléfono
        unique_count = Lead.objects.filter(
            date_entry__date=day,
            phone__isnull=False
        ).values('phone').distinct().count()
        
        # También contar leads sin teléfono como únicos
        no_phone_count = Lead.objects.filter(
            date_entry__date=day,
            phone__isnull=True
        ).count()
        
        unique_total = unique_count + no_phone_count
        
        daily_unique_counts.append({
            'day': day,
            'total': total_count,
            'unique': unique_total,
            'duplicates': total_count - unique_total
        })
    
    # Mostrar resultados
    print(f"   Días analizados: {len(daily_unique_counts)}")
    
    total_unique = sum(item['unique'] for item in daily_unique_counts)
    total_duplicates = sum(item['duplicates'] for item in daily_unique_counts)
    
    print(f"   Total leads únicos: {total_unique}")
    print(f"   Total duplicados eliminados: {total_duplicates}")
    print(f"   Reducción: {total_duplicates/total_leads_current*100:.1f}%")
    
    # 3. Mostrar comparación por día
    print("\n3. COMPARACIÓN POR DÍA (primeros 5 días):")
    for item in daily_unique_counts[:5]:
        print(f"   {item['day']}: Total={item['total']}, Únicos={item['unique']}, Duplicados={item['duplicates']}")
    
    print("\n4. COMPARACIÓN POR DÍA (últimos 5 días):")
    for item in daily_unique_counts[-5:]:
        print(f"   {item['day']}: Total={item['total']}, Únicos={item['unique']}, Duplicados={item['duplicates']}")
    
    # 4. Implementación práctica para la vista
    print("\n5. IMPLEMENTACIÓN PARA VISTA:")
    print("   Opción A: Modificar la consulta para usar leads únicos")
    print("   Opción B: Mantener datos actuales pero mostrar advertencia")
    print("   Opción C: Mostrar ambas métricas (totales y únicos)")
    
    # 5. Verificar impacto en días específicos
    print("\n6. IMPACTO EN DÍAS CON MÁS DUPLICACIÓN:")
    
    # Ordenar por mayor duplicación
    sorted_by_duplicates = sorted(daily_unique_counts, key=lambda x: x['duplicates'], reverse=True)
    
    for item in sorted_by_duplicates[:3]:
        if item['duplicates'] > 0:
            reduction_pct = item['duplicates'] / item['total'] * 100
            print(f"   {item['day']}: {item['total']} → {item['unique']} leads (-{item['duplicates']}, -{reduction_pct:.1f}%)")
    
    # 6. Recomendación
    print("\n7. RECOMENDACIÓN:")
    if total_duplicates > 0:
        print(f"   ✅ IMPLEMENTAR gráfica con leads únicos")
        print(f"   - Eliminaría {total_duplicates} duplicados ({total_duplicates/total_leads_current*100:.1f}% reducción)")
        print(f"   - Los datos serían más precisos")
        print(f"   - Coincidiría mejor con la lista (que ahora muestra leads únicos)")
    else:
        print("   ℹ️ No hay duplicados significativos, mantener lógica actual")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()