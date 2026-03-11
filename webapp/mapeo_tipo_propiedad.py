#!/usr/bin/env python
"""
Script para definir y mostrar reglas de mapeo para estandarizar tipo_propiedad
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db.models import Count

def definir_mapeo():
    """Define las reglas de mapeo para estandarizar tipo_propiedad"""
    
    mapeo = {
        # Terreno - todas las variantes
        'terreno': 'Terreno',
        'TERRENO': 'Terreno',
        'TERRENO EN VENTA': 'Terreno',
        'TERRENO URBANO EN VENTA': 'Terreno',
        'TERRENO AGRÍCOLA EN VENTA': 'Terreno',
        'TERRENO COMERCIAL EN VENTA': 'Terreno',
        'TERRENO INDUSTRIAL EN VENTA': 'Terreno',
        
        # Casa - todas las variantes
        'casa': 'Casa',
        'CASA EN VENTA': 'Casa',
        'CASA URBANA EN VENTA': 'Casa',
        'CASA DE CAMPO EN VENTA': 'Casa',
        
        # Departamento - todas las variantes
        'DEPARTAMENTO EN VENTA': 'Departamento',
        'DEPARTAMENTO FLAT EN VENTA': 'Departamento',
        'DEPARTAMENTO DUPLEX EN VENTA': 'Departamento',
        'DEPARTAMENTO PENTHOUSE EN VENTA': 'Departamento',
        'DEPARTAMENTO TRIPLEX EN VENTA': 'Departamento',
        'DEPARTAMENTO EN CONDOMINIO EN VENTA': 'Departamento',
        'MINIDEPARTAMENTO EN VENTA': 'Departamento',
        
        # Oficina
        'OFICINA EN VENTA': 'Oficina',
        
        # Otros - mapear a "Otros"
        'LOCAL COMERCIAL EN VENTA': 'Local',
        'LOCAL EN VENTA': 'Local',
        'LOCAL INDUSTRIAL EN VENTA': 'Local',
        'EDIFICIOS EN VENTA': 'Edificio',
        'HOTEL EN VENTA': 'Hotel',
        'AIRES EN VENTA': 'Otros',
        'OPORTUNIDADES EN VENTA': 'Otros',
        'OTROS EN VENTA': 'Otros',
    }
    
    return mapeo

def analizar_impacto():
    """Analiza el impacto del mapeo propuesto"""
    print("ANÁLISIS DE MAPEO PARA ESTANDARIZACIÓN DE TIPO_PROPIEDAD")
    print("=" * 70)
    
    # Obtener valores actuales
    valores = PropiedadRaw.objects.values('tipo_propiedad').annotate(
        total=Count('tipo_propiedad')
    ).order_by('tipo_propiedad')
    
    mapeo = definir_mapeo()
    
    print("\nVALORES ACTUALES Y SU MAPEO PROPUESTO:")
    print("-" * 70)
    print(f"{'Valor Original':<40} {'Mapeo':<20} {'Registros':>10}")
    print("-" * 70)
    
    total_por_mapeo = {}
    sin_mapeo = []
    
    for v in valores:
        original = v['tipo_propiedad']
        total = v['total']
        
        if original is None:
            mapeado = 'NULL (sin cambios)'
            clave = 'NULL'
        else:
            # Buscar mapeo (case-insensitive)
            mapeado = mapeo.get(original)
            if mapeado is None:
                # Intentar búsqueda case-insensitive
                for key, value in mapeo.items():
                    if key.lower() == original.lower():
                        mapeado = value
                        break
            
            if mapeado is None:
                mapeado = 'SIN MAPEO (mantener)'
                sin_mapeo.append((original, total))
                clave = 'SIN_MAPEO'
            else:
                clave = mapeado
        
        if clave not in total_por_mapeo:
            total_por_mapeo[clave] = 0
        total_por_mapeo[clave] += total
        
        print(f"{original or 'NULL':<40} {mapeado:<20} {total:>10}")
    
    print("\nRESUMEN POR CATEGORÍA ESTANDARIZADA:")
    print("-" * 70)
    for categoria, total in sorted(total_por_mapeo.items()):
        print(f"{categoria:<20} {total:>10} registros")
    
    print("\nVALORES SIN MAPEO DEFINIDO (se mantendrán igual):")
    for original, total in sin_mapeo:
        print(f"  - {original}: {total} registros")
    
    total_registros = sum(total_por_mapeo.values())
    print(f"\nTOTAL DE REGISTROS: {total_registros}")
    
    return mapeo

if __name__ == '__main__':
    analizar_impacto()