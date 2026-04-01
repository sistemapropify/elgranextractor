#!/usr/bin/env python
"""
Script para probar la corrección del problema de días.
Simula la lógica corregida de la vista.
"""
from datetime import datetime, timedelta
import calendar

def simular_logica_corregida():
    print("=== PRUEBA DE CORRECCIÓN DE DÍAS ===")
    
    # Simular fecha actual (23 de marzo de 2026)
    now = datetime(2026, 3, 23, 16, 30, 0)  # 23 de marzo, 4:30 PM
    print(f"Fecha simulada (now): {now}")
    
    # Primer día del mes
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    print(f"Primer día del mes: {first_day_of_month}")
    
    # Calcular último día del mes (solo para referencia)
    year = now.year
    month = now.month
    last_day_of_month = calendar.monthrange(year, month)[1]
    last_day_datetime = now.replace(day=last_day_of_month, hour=23, minute=59, second=59)
    
    print(f"\n=== INFORMACIÓN DEL MES ===")
    print(f"Mes actual: {month}/{year}")
    print(f"Último día del mes: {last_day_of_month}")
    print(f"Días totales en el mes: {last_day_of_month}")
    print(f"Días transcurridos hasta hoy: {now.day}")
    
    # Lógica ANTES de la corrección (generaba todos los días del mes)
    print(f"\n=== LÓGICA ANTES DE CORRECCIÓN (genera todos los días del mes) ===")
    days_antes = []
    current = first_day_of_month
    while current <= last_day_datetime:
        days_antes.append(current.strftime('%d/%m'))
        current += timedelta(days=1)
    
    print(f"Días generados: {len(days_antes)}")
    print(f"Días: {days_antes}")
    print(f"Problema: Incluye días futuros desde el {now.day+1}/{month} hasta el {last_day_of_month}/{month}")
    
    # Lógica DESPUÉS de la corrección (genera solo días hasta hoy)
    print(f"\n=== LÓGICA DESPUÉS DE CORRECCIÓN (genera solo días hasta hoy) ===")
    days_despues = []
    current = first_day_of_month
    day_counter = 0
    
    while current.date() <= now.date():
        day_counter += 1
        days_despues.append(current.strftime('%d/%m'))
        current += timedelta(days=1)
    
    print(f"Días generados: {len(days_despues)}")
    print(f"Días: {days_despues}")
    print(f"Correcto: Solo incluye días desde 01/{month} hasta {now.day:02d}/{month}")
    
    # Verificar la corrección
    print(f"\n=== VERIFICACIÓN ===")
    if len(days_despues) == now.day:
        print("✓ CORRECTO: Se generaron exactamente los días transcurridos del mes")
    else:
        print(f"✗ ERROR: Se esperaban {now.day} días, pero se generaron {len(days_despues)}")
    
    if all(int(d.split('/')[0]) <= now.day for d in days_despues):
        print("✓ CORRECTO: No se incluyen días futuros")
    else:
        print("✗ ERROR: Se incluyen días futuros")
    
    # Mostrar diferencia
    dias_futuros = [d for d in days_antes if d not in days_despues]
    print(f"\nDías futuros que ya NO se incluirán: {dias_futuros}")
    
    return days_antes, days_despues

def probar_con_diferentes_fechas():
    print(f"\n\n=== PRUEBA CON DIFERENTES FECHAS ===")
    
    fechas_prueba = [
        datetime(2026, 2, 15, 12, 0, 0),  # 15 de febrero (mes de 28 días)
        datetime(2026, 1, 31, 12, 0, 0),  # 31 de enero (último día del mes)
        datetime(2026, 4, 1, 12, 0, 0),   # 1 de abril (primer día del mes)
        datetime(2026, 12, 25, 12, 0, 0), # 25 de diciembre
    ]
    
    for fecha in fechas_prueba:
        print(f"\n--- Prueba con fecha: {fecha.date()} ---")
        first_day = fecha.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        days = []
        current = first_day
        
        while current.date() <= fecha.date():
            days.append(current.strftime('%d/%m'))
            current += timedelta(days=1)
        
        print(f"Días generados: {len(days)} (desde 01/{fecha.month:02d} hasta {fecha.day:02d}/{fecha.month:02d})")
        print(f"Último día: {days[-1] if days else 'N/A'}")

if __name__ == "__main__":
    simular_logica_corregida()
    probar_con_diferentes_fechas()
    print(f"\n=== CONCLUSIÓN ===")
    print("La corrección soluciona el problema de días que no coinciden al:")
    print("1. Generar solo los días transcurridos del mes (no días futuros)")
    print("2. Mostrar fechas en formato consistente 'dd/mm'")
    print("3. Asegurar que cada día tenga su conteo correspondiente")