#!/usr/bin/env python3
"""
Test para verificar fechas en la API de timeline mediante HTTP.
"""
import requests
import json

def test_fechas_api():
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
        print(f"Etapa {etapa['id']} ({etapa['nombre']}): fecha_inicio = {etapa.get('fecha_inicio')}")
    
    # Verificar formato de fecha
    fecha_registro = etapas[0]['fecha_inicio'] if len(etapas) > 0 else None
    if fecha_registro:
        print(f"\nFecha registro string: {fecha_registro}")
        # Verificar si contiene offset
        if 'T' in fecha_registro:
            print("✓ Contiene componente de tiempo")
            if fecha_registro.endswith('-05:00') or fecha_registro.endswith('-05'):
                print("✓ Contiene offset de Perú (-05:00)")
            elif '+' in fecha_registro.split('T')[1]:
                print("✓ Contiene offset (posiblemente no Perú)")
            else:
                print("✗ No tiene offset explícito (puede ser UTC)")
        else:
            print("✗ Solo fecha sin tiempo (puede causar offset)")
    
    # Mostrar también eventos
    events = data.get('events', [])
    if events:
        print(f"\nPrimer evento fecha_evento: {events[0].get('fecha_evento')}")
    
    # Calcular diferencia de días entre etapas
    conectores = timeline.get('conectores', [])
    print("\nConectores (días transcurridos):")
    for conector in conectores:
        print(f"  {conector['texto']}: {conector['dias_transcurridos']} días (benchmark {conector['benchmark']})")

if __name__ == '__main__':
    test_fechas_api()