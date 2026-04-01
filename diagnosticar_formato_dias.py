#!/usr/bin/env python
"""
Script para diagnosticar el formato de días que se está generando.
"""
from datetime import datetime, timedelta
import calendar

def diagnosticar_formato():
    print("=== DIAGNÓSTICO DE FORMATO DE DÍAS ===")
    
    # Simular fecha actual (23 de marzo de 2026)
    now = datetime(2026, 3, 23, 16, 30, 0)
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    print(f"Fecha simulada: {now}")
    print(f"Primer día del mes: {first_day_of_month}")
    
    # Probar diferentes formatos
    print("\n=== FORMATOS POSIBLES ===")
    
    current_day = first_day_of_month
    for i in range(5):  # Primeros 5 días
        print(f"Día {current_day.day}:")
        print(f"  strftime('%d/%m'): '{current_day.strftime('%d/%m')}'")
        print(f"  strftime('%-d/%-m'): '{current_day.strftime('%d/%m').lstrip('0')}'")
        print(f"  strftime('%d/%m'): día con cero: {current_day.strftime('%d')}, mes con cero: {current_day.strftime('%m')}")
        print(f"  f-string: f'{current_day.day}/{current_day.month}': '{current_day.day}/{current_day.month}'")
        print(f"  f-string con cero: f'{current_day.day:02d}/{current_day.month:02d}': '{current_day.day:02d}/{current_day.month:02d}'")
        current_day += timedelta(days=1)
    
    # Verificar si hay error de índice
    print("\n=== VERIFICACIÓN DE ÍNDICE ===")
    current_day = first_day_of_month
    day_counter = 0
    while current_day.date() <= now.date():
        day_counter += 1
        # Formato actual usado en la vista
        formatted = current_day.strftime('%d/%m')
        # Posible error: usar day_counter-1 como día
        wrong_format = f"{day_counter-1}/{current_day.month}"
        print(f"Día {day_counter}: formato correcto '{formatted}', error posible '{wrong_format}'")
        current_day += timedelta(days=1)
    
    # Verificar datos de ejemplo en el template
    print("\n=== DATOS DE EJEMPLO EN TEMPLATE ===")
    example_days = ['01/03', '02/03', '03/03', '04/03', '05/03', '06/03', '07/03', '08/03', '09/03', '10/03']
    print(f"Datos de ejemplo: {example_days}")
    print("Estos son correctos (día con cero a la izquierda)")
    
    # Verificar si el problema es en JavaScript
    print("\n=== POSIBLE PROBLEMA EN JAVASCRIPT ===")
    print("Si los datos llegan como '01/03' pero Chart.js los muestra como '0/3',")
    print("podría ser un problema de parsing o formato en Chart.js.")
    
    return True

if __name__ == "__main__":
    diagnosticar_formato()