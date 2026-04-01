#!/usr/bin/env python3
"""
Simular cómo el frontend JavaScript formatea las fechas.
"""
import datetime
import re

def js_date_to_local(date_str):
    """Simular new Date(date_str).toLocaleDateString('es-PE')"""
    # Parsear la cadena ISO
    # Simplificación: asumir que el navegador parsea correctamente
    # Usaremos datetime para obtener la fecha
    try:
        if 'T' in date_str:
            # Tiene componente de tiempo
            dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            # Solo fecha
            dt = datetime.datetime.fromisoformat(date_str)
            # JavaScript interpreta como UTC medianoche
            dt = dt.replace(tzinfo=datetime.timezone.utc)
    except Exception as e:
        print(f"Error parseando {date_str}: {e}")
        return None
    
    # Convertir a zona horaria de Perú (UTC-5)
    peru_tz = datetime.timezone(datetime.timedelta(hours=-5))
    dt_peru = dt.astimezone(peru_tz)
    
    # Formatear como 'es-PE' (dd/mm/yyyy)
    formatted = dt_peru.strftime('%d/%m/%Y')
    return formatted

def test():
    fechas = [
        "2026-01-07T12:00:00-05:00",
        "2026-01-07",
        "2026-01-21",
        "2026-01-07T00:00:00Z",
    ]
    
    for fecha in fechas:
        formatted = js_date_to_local(fecha)
        print(f"{fecha} -> {formatted}")

if __name__ == '__main__':
    test()