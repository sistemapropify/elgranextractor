#!/usr/bin/env python
"""
Script para verificar la importación de propiedades.
"""
import os
import sys

# Configurar Django
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from ingestas.models import PropiedadRaw
from django.db.models import Count

def main():
    print("=== VERIFICACIÓN DE IMPORTACIÓN ===")
    
    # Contar registros
    total = PropiedadRaw.objects.count()
    print(f"Total registros en PropiedadRaw: {total}")
    
    if total == 0:
        print("ERROR: No hay registros importados.")
        return
    
    # Estadísticas por tipo de propiedad
    print("\nDistribución por tipo de propiedad:")
    tipos_stats = PropiedadRaw.objects.values('tipo_propiedad').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for stat in tipos_stats:
        tipo = stat['tipo_propiedad'] or 'Sin tipo'
        print(f"  {tipo}: {stat['count']}")
    
    # Estadísticas por portal
    print("\nDistribución por portal:")
    portales_stats = PropiedadRaw.objects.values('portal').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for stat in portales_stats:
        portal = stat['portal'] or 'Sin portal'
        print(f"  {portal}: {stat['count']}")
    
    # Estadísticas por departamento
    print("\nTop 5 departamentos:")
    deptos_stats = PropiedadRaw.objects.values('departamento').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    for stat in deptos_stats:
        depto = stat['departamento'] or 'Sin departamento'
        print(f"  {depto}: {stat['count']}")
    
    # Ejemplos de registros
    print("\nEjemplos de registros importados (primeros 3):")
    for p in PropiedadRaw.objects.all()[:3]:
        print(f"  - ID {p.id}: {p.tipo_propiedad} en {p.departamento}, {p.provincia}")
        print(f"    Precio: {p.precio_usd}, Área: {p.area_terreno} m²")
        print(f"    Portal: {p.portal}, URL: {p.url_propiedad[:50]}...")
    
    # Verificar campos importantes
    print("\nVerificación de campos:")
    campos_verificar = ['precio_usd', 'area_terreno', 'coordenadas', 'identificador_externo']
    for campo in campos_verificar:
        no_nulos = PropiedadRaw.objects.exclude(**{campo: None}).count()
        porcentaje = (no_nulos / total * 100) if total > 0 else 0
        print(f"  {campo}: {no_nulos} no nulos ({porcentaje:.1f}%)")
    
    print(f"\n¡Importación verificada exitosamente! Se importaron {total} registros.")

if __name__ == '__main__':
    main()