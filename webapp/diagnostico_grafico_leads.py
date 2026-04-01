#!/usr/bin/env python
"""
Diagnóstico del gráfico de leads - verifica discrepancias entre datos reales y gráfico
"""
import os
import sys
import django
import json
from datetime import datetime, timedelta
import calendar

# Configurar Django - ajustar ruta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from analisis_crm.models import Lead
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

def verificar_datos_5_marzo():
    """Verificar específicamente los leads del 5 de marzo"""
    print("=== VERIFICACIÓN DE LEADS DEL 5 DE MARZO ===")
    
    # Fecha específica: 5 de marzo de 2026
    fecha_5_marzo = datetime(2026, 3, 5).date()
    
    # Método 1: Contar directamente con filter
    leads_directo = Lead.objects.filter(date_entry__date=fecha_5_marzo)
    count_directo = leads_directo.count()
    print(f"1. Leads con date_entry exactamente el 5/3/2026 (filter directo): {count_directo}")
    
    # Método 2: Usar TruncDate como lo hace la vista
    from django.db.models import Q
    leads_trunc = Lead.objects.annotate(
        day=TruncDate('date_entry')
    ).filter(day=fecha_5_marzo)
    count_trunc = leads_trunc.count()
    print(f"2. Leads con TruncDate('date_entry') = 5/3/2026: {count_trunc}")
    
    # Método 3: Verificar rango de fechas (todo el día 5)
    fecha_inicio = datetime(2026, 3, 5, 0, 0, 0)
    fecha_fin = datetime(2026, 3, 5, 23, 59, 59)
    leads_rango = Lead.objects.filter(
        date_entry__gte=fecha_inicio,
        date_entry__lte=fecha_fin
    )
    count_rango = leads_rango.count()
    print(f"3. Leads con date_entry entre 5/3/2026 00:00 y 23:59: {count_rango}")
    
    # Mostrar algunos leads para verificar
    print(f"\n4. Primeros 5 leads encontrados (método directo):")
    for i, lead in enumerate(leads_directo[:5]):
        print(f"   {i+1}. ID: {lead.id}, Nombre: {lead.full_name}, date_entry: {lead.date_entry}")
    
    # Verificar si hay leads con date_entry nulo
    leads_null = Lead.objects.filter(date_entry__isnull=True).count()
    print(f"\n5. Leads con date_entry NULL: {leads_null}")
    
    return count_directo

def verificar_agregacion_mensual():
    """Verificar la agregación mensual completa"""
    print("\n=== VERIFICACIÓN DE AGRECACIÓN MENSUAL ===")
    
    now = timezone.now()
    year = now.year
    month = now.month
    
    print(f"Mes actual: {month}/{year}")
    
    # Obtener primer y último día del mes
    first_day = datetime(year, month, 1).date()
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num).date()
    
    print(f"Primer día: {first_day}")
    print(f"Último día: {last_day}")
    
    # Obtener todos los leads del mes
    leads_mes = Lead.objects.filter(
        date_entry__date__gte=first_day,
        date_entry__date__lte=last_day
    )
    
    # Agrupar por día manualmente
    from collections import defaultdict
    conteo_manual = defaultdict(int)
    
    for lead in leads_mes:
        if lead.date_entry:
            fecha = lead.date_entry.date()
            conteo_manual[fecha] += 1
    
    print(f"\nConteo manual por día:")
    dias_ordenados = sorted(conteo_manual.keys())
    for dia in dias_ordenados:
        print(f"  {dia.strftime('%d/%m')}: {conteo_manual[dia]} leads")
    
    # Comparar con el método de la vista
    print(f"\n=== COMPARACIÓN CON MÉTODO DE LA VISTA ===")
    
    # Método similar a la vista
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    
    daily_leads = Lead.objects.filter(
        date_entry__date__gte=first_day,
        date_entry__date__lte=last_day
    ).annotate(
        day=TruncDate('date_entry')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    print(f"Resultado de daily_leads (método vista):")
    for entry in daily_leads:
        print(f"  {entry['day']}: {entry['count']}")
    
    # Verificar discrepancia para el 5 de marzo
    fecha_5_marzo = datetime(2026, 3, 5).date()
    count_vista = 0
    for entry in daily_leads:
        if entry['day'] == fecha_5_marzo:
            count_vista = entry['count']
            break
    
    print(f"\nConteo para 5/3/2026:")
    print(f"  - Manual: {conteo_manual.get(fecha_5_marzo, 0)}")
    print(f"  - Vista: {count_vista}")
    
    return conteo_manual

def verificar_timezone():
    """Verificar problemas de timezone"""
    print("\n=== VERIFICACIÓN DE TIMEZONE ===")
    
    # Verificar configuración de timezone
    from django.conf import settings
    print(f"TIME_ZONE en settings: {settings.TIME_ZONE}")
    print(f"USE_TZ en settings: {settings.USE_TZ}")
    
    # Verificar now() con y sin timezone
    now_naive = datetime.now()
    now_tz = timezone.now()
    print(f"datetime.now() (naive): {now_naive}")
    print(f"timezone.now() (aware): {now_tz}")
    
    # Verificar un lead de ejemplo
    lead_ejemplo = Lead.objects.first()
    if lead_ejemplo and lead_ejemplo.date_entry:
        print(f"\nLead de ejemplo:")
        print(f"  ID: {lead_ejemplo.id}")
        print(f"  date_entry: {lead_ejemplo.date_entry}")
        print(f"  date_entry tzinfo: {lead_ejemplo.date_entry.tzinfo}")
        print(f"  date_entry.date(): {lead_ejemplo.date_entry.date()}")

def main():
    print("DIAGNÓSTICO DE GRÁFICO DE LEADS")
    print("=" * 50)
    
    # Verificar conteo total
    total_leads = Lead.objects.count()
    print(f"Total de leads en la base de datos: {total_leads}")
    
    # Verificar específicamente el 5 de marzo
    count_5_marzo = verificar_datos_5_marzo()
    
    # Verificar agregación mensual
    conteo_manual = verificar_agregacion_mensual()
    
    # Verificar timezone
    verificar_timezone()
    
    print("\n" + "=" * 50)
    print("RESUMEN:")
    print(f"- Leads totales: {total_leads}")
    print(f"- Leads del 5/3/2026: {count_5_marzo}")
    
    if count_5_marzo != 12:
        print(f"¡ALERTA! El conteo del 5/3/2026 ({count_5_marzo}) no coincide con lo esperado (12)")
        print("Posibles causas:")
        print("1. Problema de timezone en las fechas")
        print("2. Algunos leads tienen date_entry NULL")
        print("3. Error en el filtro de fecha")
        print("4. Diferencia entre fecha almacenada y fecha mostrada")
    else:
        print("✓ El conteo del 5/3/2026 coincide con lo esperado")

if __name__ == '__main__':
    main()