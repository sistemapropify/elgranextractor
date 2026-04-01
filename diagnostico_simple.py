#!/usr/bin/env python
"""
Diagnóstico simple del problema de días.
"""
from datetime import datetime, timedelta
import calendar

def diagnosticar_formato_fechas():
    print("=== DIAGNÓSTICO DE FORMATO DE FECHAS ===")
    
    # Fecha actual
    now = datetime.now()
    print(f"Fecha actual del sistema: {now}")
    print(f"Fecha formateada 'dd/mm': {now.strftime('%d/%m')}")
    print(f"Fecha formateada 'mm/dd': {now.strftime('%m/%d')}")
    print(f"Fecha formateada 'd/m': {now.strftime('%d/%m')}")
    
    # Primer día del mes
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    print(f"\nPrimer día del mes: {first_day}")
    
    # Último día del mes
    last_day_num = calendar.monthrange(now.year, now.month)[1]
    last_day = now.replace(day=last_day_num, hour=23, minute=59, second=59)
    print(f"Último día del mes: {last_day}")
    print(f"Número de días en el mes: {last_day_num}")
    
    # Generar todos los días del mes
    print(f"\n=== DÍAS DEL MES ACTUAL ===")
    current = first_day
    days = []
    day_count = 0
    
    while current <= last_day:
        day_count += 1
        day_str = current.strftime('%d/%m')
        days.append(day_str)
        print(f"Día {day_count}: {day_str} (original: {current.date()})")
        current += timedelta(days=1)
    
    print(f"\nTotal de días generados: {len(days)}")
    print(f"Días: {days}")
    
    # Verificar problemas comunes
    print(f"\n=== PROBLEMAS COMUNES ===")
    
    # 1. Días duplicados
    if len(set(days)) != len(days):
        print("⚠️ PROBLEMA: Hay días duplicados")
    
    # 2. Días faltantes
    expected_days = last_day_num
    if len(days) != expected_days:
        print(f"⚠️ PROBLEMA: Se esperaban {expected_days} días, pero hay {len(days)}")
    
    # 3. Formato inconsistente
    for i, day in enumerate(days):
        parts = day.split('/')
        if len(parts) != 2:
            print(f"⚠️ PROBLEMA: Formato incorrecto en día {day}")
        day_num, month_num = int(parts[0]), int(parts[1])
        if month_num != now.month:
            print(f"⚠️ PROBLEMA: Mes incorrecto en día {day} (esperado: {now.month})")
    
    # 4. Días futuros en el mes
    today = now.date()
    future_days = [d for d in days if int(d.split('/')[0]) > today.day]
    if future_days:
        print(f"⚠️ ADVERTENCIA: Se están generando días futuros: {future_days}")
    
    return days

if __name__ == "__main__":
    diagnosticar_formato_fechas()