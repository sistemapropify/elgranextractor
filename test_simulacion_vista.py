#!/usr/bin/env python3
"""
Script para simular lo que hace la vista dashboard_calidad_cartera
y entender la duplicación en los conteos por tipo.
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

def simular_calculo_tipos():
    """Simula el cálculo de stats_por_tipo como lo hace la vista."""
    
    print("=== SIMULACIÓN DE CÁLCULO DE TIPOS EN LA VISTA ===")
    
    # Obtener todas las propiedades (como lo hace la vista)
    propiedades = PropifaiProperty.objects.all()
    total = propiedades.count()
    print(f"Total propiedades: {total}")
    
    # Simular propiedades_con_score (todas las propiedades con score calculado)
    propiedades_con_score = []
    for prop in propiedades:
        # Simular cálculo de score (simplificado)
        prop.completitud_score = 80  # Valor de ejemplo
        propiedades_con_score.append(prop)
    
    print(f"Propiedades con score calculado: {len(propiedades_con_score)}")
    
    # Calcular stats por tipo como lo hace la vista (líneas 643-675)
    tipo_scores = {}
    for prop in propiedades_con_score:
        tipo = prop.availability_status or 'sinestado'
        if tipo not in tipo_scores:
            tipo_scores[tipo] = {
                'num_props': 0,
                'sum_completitud': 0
            }
        stats = tipo_scores[tipo]
        stats['num_props'] += 1
        stats['sum_completitud'] += prop.completitud_score
    
    print("\nResultados del cálculo tipo_scores (inglés):")
    for tipo, stats in tipo_scores.items():
        completitud_prom = stats['sum_completitud'] / stats['num_props'] if stats['num_props'] else 0
        print(f"  '{tipo}': {stats['num_props']} propiedades, completitud: {completitud_prom:.1f}%")
    
    # Verificar si hay mapeo a español en algún lugar
    print("\nVerificando mapeo inglés-español:")
    estado_a_espanol = {
        'available': 'disponible',
        'sold': 'vendido',
        'reserved': 'reservado',
        'catchment': 'catchment',
        'paused': 'pausado',
        'unavailable': 'nodisponible',
    }
    
    # Verificar si algún estado en tipo_scores está en español
    estados_en_espanol = []
    for tipo in tipo_scores.keys():
        if tipo in estado_a_espanol.values():
            estados_en_espanol.append(tipo)
    
    if estados_en_espanol:
        print(f"  Estados en español encontrados: {estados_en_espanol}")
    else:
        print("  No se encontraron estados en español en tipo_scores")
    
    # Verificar conteo de borradores
    props_borradores = propiedades.filter(is_draft=True).count()
    print(f"\nPropiedades borrador (is_draft=True): {props_borradores}")
    
    # Verificar conteo de disponibles (no borradores)
    props_disponibles = propiedades.filter(is_draft=False).count()
    print(f"Propiedades disponibles (no borradores): {props_disponibles}")
    
    # Verificar si hay propiedades con availability_status en español
    print("\nBuscando propiedades con availability_status en español:")
    estados_unicos = propiedades.values_list('availability_status', flat=True).distinct()
    estados_espanol_en_db = []
    for estado in estados_unicos:
        if estado and estado in estado_a_espanol.values():
            estados_espanol_en_db.append(estado)
    
    if estados_espanol_en_db:
        print(f"  Estados en español encontrados en la base de datos: {estados_espanol_en_db}")
        for estado in estados_espanol_en_db:
            count = propiedades.filter(availability_status=estado).count()
            print(f"    '{estado}': {count} propiedades")
    else:
        print("  No se encontraron estados en español en la base de datos")

if __name__ == '__main__':
    simular_calculo_tipos()