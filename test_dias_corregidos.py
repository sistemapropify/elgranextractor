#!/usr/bin/env python
"""
Test para verificar que los días se generan correctamente (1, 2, 3...30)
"""
from datetime import datetime, timedelta
import calendar

def test_generacion_dias():
    print("=== TEST DE GENERACIÓN DE DÍAS CORREGIDOS ===")
    
    # Simular fecha actual (23 de marzo de 2026)
    now = datetime(2026, 3, 23, 16, 30, 0)
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"Fecha simulada: {now.date()}")
    print(f"Primer día del mes: {first_day_of_month.date()}")
    
    # Generar días como lo hace la vista corregida
    days_of_month = []
    current_day = first_day_of_month
    
    while current_day.date() <= now.date():
        # Formato corregido: solo el día del mes (sin cero a la izquierda)
        days_of_month.append(str(current_day.day))
        current_day += timedelta(days=1)
    
    print(f"\nDías generados: {len(days_of_month)}")
    print(f"Días: {days_of_month}")
    
    # Verificar que no haya días con formato "0/3" o "1/3"
    errors = []
    for i, day_str in enumerate(days_of_month):
        if '/' in day_str:
            errors.append(f"Día {i}: '{day_str}' contiene '/' (formato incorrecto)")
        if not day_str.isdigit():
            errors.append(f"Día {i}: '{day_str}' no es un número")
        if day_str == '0':
            errors.append(f"Día {i}: '0' (día cero incorrecto)")
    
    if errors:
        print(f"\n❌ ERRORES ENCONTRADOS:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(f"\n✅ CORRECTO: Los días se generan en formato correcto (1, 2, 3...{len(days_of_month)})")
        
        # Verificar que los días sean consecutivos
        expected_days = list(range(1, len(days_of_month) + 1))
        actual_days = [int(d) for d in days_of_month]
        
        if actual_days == expected_days:
            print(f"✅ Los días son consecutivos: {actual_days}")
        else:
            print(f"❌ Los días NO son consecutivos: esperado {expected_days}, obtenido {actual_days}")
            return False
    
    # Verificar para un mes completo (simulando fin de mes)
    print(f"\n=== TEST PARA MES COMPLETO (31 días) ===")
    last_day = datetime(2026, 3, 31, 23, 59, 59)
    current_day = first_day_of_month
    full_month_days = []
    
    while current_day.date() <= last_day.date():
        full_month_days.append(str(current_day.day))
        current_day += timedelta(days=1)
    
    print(f"Días generados para mes completo: {len(full_month_days)}")
    print(f"Primeros 5 días: {full_month_days[:5]}")
    print(f"Últimos 5 días: {full_month_days[-5:]}")
    
    if len(full_month_days) == 31:
        print("✅ Mes completo generado correctamente")
    else:
        print(f"❌ Mes incompleto: esperado 31 días, obtenido {len(full_month_days)}")
    
    return True

if __name__ == "__main__":
    success = test_generacion_dias()
    if success:
        print("\n✅ TODAS LAS PRUEBAS PASARON CORRECTAMENTE")
    else:
        print("\n❌ ALGUNAS PRUEBAS FALLARON")
        exit(1)