#!/usr/bin/env python
"""
Script para identificar los valores actuales del campo tipo_propiedad
"""
import os
import sys
import django

# Configurar Django - ajustar path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db.models import Count

def main():
    print("Analizando valores de tipo_propiedad en la base de datos...")
    print("=" * 60)
    
    # Obtener valores distintos con conteo
    valores = PropiedadRaw.objects.values('tipo_propiedad').annotate(
        total=Count('tipo_propiedad')
    ).order_by('tipo_propiedad')
    
    print(f"{'Valor':<40} {'Registros':>10}")
    print("-" * 60)
    
    total_registros = 0
    for v in valores:
        tipo = v['tipo_propiedad']
        total = v['total']
        total_registros += total
        print(f"{tipo or 'NULL':<40} {total:>10}")
    
    print("-" * 60)
    print(f"{'TOTAL':<40} {total_registros:>10}")
    
    # También mostrar algunos ejemplos de cada tipo
    print("\nEjemplos de cada valor (primeros 5):")
    print("=" * 60)
    for v in valores:
        tipo = v['tipo_propiedad']
        if tipo:
            ejemplos = PropiedadRaw.objects.filter(tipo_propiedad=tipo)[:5]
            print(f"\n{tipo} ({len(ejemplos)} ejemplos):")
            for i, ejemplo in enumerate(ejemplos, 1):
                print(f"  {i}. ID: {ejemplo.id}, Desc: {ejemplo.descripcion[:80] if ejemplo.descripcion else 'N/A'}...")
    
    # Contar registros nulos
    nulos = PropiedadRaw.objects.filter(tipo_propiedad__isnull=True).count()
    print(f"\nRegistros con tipo_propiedad NULL: {nulos}")

if __name__ == '__main__':
    main()