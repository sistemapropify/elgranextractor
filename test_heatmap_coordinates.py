#!/usr/bin/env python
"""
Script para verificar las coordenadas de las propiedades en el heatmap
y calcular el centro correcto para el mapa.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def main():
    print("=== VERIFICACIÓN DE COORDENADAS PARA HEATMAP ===")
    
    # Obtener todas las propiedades con coordenadas
    propiedades = PropiedadRaw.objects.filter(
        coordenadas__isnull=False
    ).exclude(coordenadas='')
    
    total = propiedades.count()
    print(f"Total propiedades con coordenadas: {total}")
    
    if total == 0:
        print("ERROR: No hay propiedades con coordenadas")
        return
    
    # Analizar coordenadas
    latitudes = []
    longitudes = []
    coordenadas_validas = 0
    
    for prop in propiedades[:100]:  # Muestra de 100 propiedades
        try:
            coords = prop.coordenadas.split(',')
            if len(coords) >= 2:
                lat = float(coords[0].strip())
                lng = float(coords[1].strip())
                latitudes.append(lat)
                longitudes.append(lng)
                coordenadas_validas += 1
        except (ValueError, AttributeError, TypeError):
            continue
    
    if coordenadas_validas == 0:
        print("ERROR: No se pudieron parsear coordenadas válidas")
        return
    
    # Calcular estadísticas
    min_lat = min(latitudes)
    max_lat = max(latitudes)
    min_lng = min(longitudes)
    max_lng = max(longitudes)
    avg_lat = sum(latitudes) / len(latitudes)
    avg_lng = sum(longitudes) / len(longitudes)
    
    print(f"\n=== ESTADÍSTICAS DE COORDENADAS ===")
    print(f"Latitud mínima: {min_lat}")
    print(f"Latitud máxima: {max_lat}")
    print(f"Longitud mínima: {min_lng}")
    print(f"Longitud máxima: {max_lng}")
    print(f"Latitud promedio: {avg_lat}")
    print(f"Longitud promedio: {avg_lng}")
    
    # Determinar ubicación aproximada
    print(f"\n=== UBICACIÓN APROXIMADA ===")
    # Arequipa: lat ~ -16.4, lng ~ -71.5
    # Lima: lat ~ -12.0, lng ~ -77.0
    if min_lat > -13 and max_lat < -11:
        print("Ubicación: LIMA (Perú)")
    elif min_lat > -17 and max_lat < -16:
        print("Ubicación: AREQUIPA (Perú)")
    else:
        print("Ubicación: Desconocida")
    
    # Calcular centro para el mapa
    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2
    
    print(f"\n=== CENTRO RECOMENDADO PARA EL MAPA ===")
    print(f"Centro: ({center_lat:.6f}, {center_lng:.6f})")
    
    # Calcular zoom aproximado
    lat_diff = max_lat - min_lat
    lng_diff = max_lng - min_lng
    max_diff = max(lat_diff, lng_diff)
    
    print(f"Diferencia latitud: {lat_diff:.4f}")
    print(f"Diferencia longitud: {lng_diff:.4f}")
    print(f"Diferencia máxima: {max_diff:.4f}")
    
    # Recomendar zoom
    if max_diff < 0.01:
        zoom = 16
    elif max_diff < 0.02:
        zoom = 15
    elif max_diff < 0.05:
        zoom = 14
    elif max_diff < 0.1:
        zoom = 13
    elif max_diff < 0.2:
        zoom = 12
    elif max_diff < 0.5:
        zoom = 11
    elif max_diff < 1.0:
        zoom = 10
    elif max_diff < 2.0:
        zoom = 9
    else:
        zoom = 8
    
    print(f"\n=== CONFIGURACIÓN RECOMENDADA PARA GOOGLE MAPS ===")
    print(f"center: {{ lat: {center_lat:.6f}, lng: {center_lng:.6f} }}")
    print(f"zoom: {zoom}")
    
    # Mostrar algunas coordenadas de ejemplo
    print(f"\n=== COORDENADAS DE EJEMPLO (primeras 5) ===")
    for i, (lat, lng) in enumerate(zip(latitudes[:5], longitudes[:5])):
        print(f"{i+1}. ({lat:.6f}, {lng:.6f})")

if __name__ == '__main__':
    main()