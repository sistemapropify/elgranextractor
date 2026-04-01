#!/usr/bin/env python3
"""
Test final para verificar que todas las fechas tengan offset de Perú.
"""
import requests
import json

def test():
    url = "http://localhost:8000/propifai/api/property/2/timeline/"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return
    
    timeline = data.get('timeline', {})
    etapas = timeline.get('etapas', [])
    
    print("Fechas en etapas:")
    for etapa in etapas:
        fecha = etapa.get('fecha_inicio')
        print(f"Etapa {etapa['id']} ({etapa['nombre']}): {fecha}")
        if fecha and 'T' in fecha:
            if fecha.endswith('-05:00'):
                print("  -> OK: tiene offset de Perú")
            else:
                print("  -> WARNING: sin offset de Perú")
    
    events = data.get('events', [])
    if events:
        print(f"\nPrimer evento fecha_evento: {events[0].get('fecha_evento')}")
        if events[0].get('fecha_evento') and 'T' in events[0].get('fecha_evento'):
            if events[0]['fecha_evento'].endswith('-05:00'):
                print("  -> OK: tiene offset de Perú")
            else:
                print("  -> WARNING: sin offset de Perú")
    
    # Simular conversión frontend
    print("\nSimulación de conversión frontend (toLocaleDateString):")
    for etapa in etapas[:3]:  # solo primeras 3
        fecha = etapa.get('fecha_inicio')
        if not fecha:
            continue
        # Simulación simple: extraer fecha si tiene offset
        if 'T' in fecha:
            # Asumir que el navegador parsea correctamente
            # Solo imprimir la parte de fecha
            fecha_part = fecha.split('T')[0]
            print(f"  Etapa {etapa['id']}: {fecha_part}")

if __name__ == '__main__':
    test()