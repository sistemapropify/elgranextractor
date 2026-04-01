#!/usr/bin/env python3
"""
Script para verificar que todos los conteos en el dashboard sean consistentes.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

django.setup()

from propifai.models import PropifaiProperty
from django.db import connections

def verificar_conteos():
    """Verifica la consistencia de todos los conteos."""
    
    print("=== VERIFICACIÓN DE CONSISTENCIA DE CONTEO ===")
    
    # Obtener todas las propiedades
    propiedades = PropifaiProperty.objects.all()
    total_db = propiedades.count()
    print(f"1. Total propiedades en la base de datos: {total_db}")
    
    # Contar por disponibilidad (no borradores)
    props_disponibles = propiedades.filter(is_draft=False).count()
    props_borradores = propiedades.filter(is_draft=True).count()
    print(f"2. Propiedades disponibles (no borradores): {props_disponibles}")
    print(f"3. Propiedades borrador: {props_borradores}")
    print(f"   Verificación: {props_disponibles} + {props_borradores} = {props_disponibles + props_borradores} (debería ser {total_db})")
    
    # Contar por availability_status
    print("\n4. Conteo por availability_status:")
    estados = propiedades.values_list('availability_status', flat=True).distinct()
    total_por_estado = 0
    for estado in estados:
        if estado:
            count = propiedades.filter(availability_status=estado).count()
            print(f"   '{estado}': {count}")
            total_por_estado += count
        else:
            count = propiedades.filter(availability_status__isnull=True).count()
            print(f"   'None/sinestado': {count}")
            total_por_estado += count
    
    print(f"   Total sumando estados: {total_por_estado} (debería ser {total_db})")
    
    # Verificar propiedades con district
    print("\n5. Propiedades con district definido:")
    props_con_distrito = propiedades.exclude(district__isnull=True).exclude(district='').count()
    props_sin_distrito = total_db - props_con_distrito
    print(f"   Con distrito: {props_con_distrito}")
    print(f"   Sin distrito: {props_sin_distrito}")
    
    # Verificar propiedades con coordinates
    print("\n6. Propiedades con coordinates:")
    props_con_coordinates = propiedades.exclude(coordinates__isnull=True).exclude(coordinates='').count()
    props_sin_coordinates = total_db - props_con_coordinates
    print(f"   Con coordinates: {props_con_coordinates}")
    print(f"   Sin coordinates: {props_sin_coordinates}")
    
    # Simular cálculo de distritos como lo hace la vista
    print("\n7. Simulación de cálculo por distrito (top 10):")
    distrito_counts = {}
    for prop in propiedades:
        district = prop.district
        if not district:
            district = 'Sin distrito'
        distrito_counts[district] = distrito_counts.get(district, 0) + 1
    
    # Ordenar y tomar top 10
    distritos_ordenados = sorted(distrito_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    total_distritos_top10 = sum(count for _, count in distritos_ordenados)
    
    for distrito, count in distritos_ordenados:
        print(f"   '{distrito}': {count}")
    
    print(f"   Total en top 10 distritos: {total_distritos_top10}")
    print(f"   Total propiedades con distrito: {props_con_distrito}")
    print(f"   Diferencia: {props_con_distrito - total_distritos_top10} propiedades no están en top 10")
    
    # Verificar la discrepancia reportada por el usuario
    print("\n8. Análisis de discrepancia reportada:")
    print(f"   - Usuario reporta: 'en la matriz de calidad hay 54 propiedades'")
    print(f"   - Disponibles (available): {propiedades.filter(availability_status='available').count()}")
    print(f"   - ¿Coincide? {'SÍ' if propiedades.filter(availability_status='available').count() == 54 else 'NO'}")
    
    # Verificar si hay propiedades con availability_status en español
    estado_a_espanol = {
        'available': 'disponible',
        'sold': 'vendido',
        'reserved': 'reservado',
        'catchment': 'catchment',
        'paused': 'pausado',
        'unavailable': 'nodisponible',
    }
    
    print("\n9. Verificación de estados en español:")
    for eng, esp in estado_a_espanol.items():
        count_eng = propiedades.filter(availability_status=eng).count()
        count_esp = propiedades.filter(availability_status=esp).count()
        if count_esp > 0:
            print(f"   ADVERTENCIA: Estado '{esp}' encontrado en la base de datos: {count_esp} propiedades")
            print(f"     Equivalente inglés '{eng}': {count_eng} propiedades")
    
    # Resumen final
    print("\n=== RESUMEN ===")
    print(f"Total propiedades: {total_db}")
    print(f"Disponibles (no borradores): {props_disponibles}")
    print(f"Con estado 'available': {propiedades.filter(availability_status='available').count()}")
    print(f"Con distrito definido: {props_con_distrito}")
    
    if total_db != total_por_estado:
        print(f"¡ADVERTENCIA! La suma de estados ({total_por_estado}) no coincide con el total ({total_db})")
    
    if props_disponibles + props_borradores != total_db:
        print(f"¡ADVERTENCIA! La suma de disponibles + borradores no coincide con el total")

if __name__ == '__main__':
    verificar_conteos()