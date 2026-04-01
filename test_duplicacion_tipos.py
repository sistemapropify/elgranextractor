#!/usr/bin/env python3
"""
Script para analizar la duplicación en los conteos por tipo (inglés/español)
en el dashboard de calidad de cartera.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

django.setup()

from propifai.models import PropifaiProperty as Property
from django.db import connections

def analizar_duplicacion_tipos():
    """Analiza los tipos de propiedades y sus conteos."""
    
    print("=== ANÁLISIS DE DUPLICACIÓN EN TIPOS ===")
    
    # Obtener todas las propiedades
    propiedades = Property.objects.all()
    total = propiedades.count()
    print(f"Total propiedades en la base de datos: {total}")
    
    # Contar por availability_status (inglés)
    conteo_ingles = {}
    for prop in propiedades:
        status = prop.availability_status or 'sinestado'
        conteo_ingles[status] = conteo_ingles.get(status, 0) + 1
    
    print("\nConteo por availability_status (inglés):")
    for status, count in sorted(conteo_ingles.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")
    
    # Verificar si hay propiedades con el mismo estado en inglés y español
    # Mapeo de inglés a español
    mapeo_ingles_espanol = {
        'available': 'disponible',
        'sold': 'vendido',
        'reserved': 'reservado',
        'catchment': 'catchment',
        'paused': 'pausado',
        'unavailable': 'nodisponible',
    }
    
    # Verificar si hay propiedades con estados que podrían ser duplicados
    print("\nVerificación de posibles duplicados:")
    for eng, esp in mapeo_ingles_espanol.items():
        count_eng = conteo_ingles.get(eng, 0)
        count_esp = conteo_ingles.get(esp, 0)
        if count_eng > 0 and count_esp > 0:
            print(f"  ADVERTENCIA: Tanto '{eng}' ({count_eng}) como '{esp}' ({count_esp}) existen")
    
    # Verificar también los estados en español que no tienen equivalente en inglés
    estados_espanol = [esp for esp in conteo_ingles.keys() if esp in mapeo_ingles_espanol.values()]
    for esp in estados_espanol:
        # Encontrar la clave en inglés correspondiente
        eng_correspondiente = None
        for eng, esp_map in mapeo_ingles_espanol.items():
            if esp_map == esp:
                eng_correspondiente = eng
                break
        
        if eng_correspondiente:
            count_esp = conteo_ingles.get(esp, 0)
            count_eng = conteo_ingles.get(eng_correspondiente, 0)
            if count_esp > 0 and count_eng > 0:
                print(f"  ADVERTENCIA: '{esp}' ({count_esp}) y '{eng_correspondiente}' ({count_eng}) ambos existen")
    
    # Verificar el total sumando todos los estados
    total_por_estado = sum(conteo_ingles.values())
    print(f"\nTotal sumando todos los estados: {total_por_estado}")
    print(f"Total propiedades: {total}")
    
    if total_por_estado != total:
        print(f"  DISCREPANCIA: La suma de estados ({total_por_estado}) no coincide con el total ({total})")
    
    # Verificar propiedades sin estado
    sin_estado = conteo_ingles.get('sinestado', 0)
    print(f"\nPropiedades sin estado (sinestado): {sin_estado}")
    
    # Verificar borradores
    borradores = propiedades.filter(is_draft=True).count()
    print(f"Propiedades borrador (is_draft=True): {borradores}")

if __name__ == '__main__':
    analizar_duplicacion_tipos()