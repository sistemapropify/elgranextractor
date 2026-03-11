#!/usr/bin/env python
"""
Script para explorar mapeo entre IDs de distrito y nombres.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty

def explorar_distritos():
    """Explorar distritos en propiedades y requerimientos."""
    print("=== Exploración de Distritos ===")
    
    # Distritos únicos en propiedades (IDs numéricos)
    distritos_prop = PropifaiProperty.objects.filter(
        district__isnull=False
    ).exclude(
        district=''
    ).values_list('district', flat=True).distinct()
    
    distritos_prop_list = list(distritos_prop)
    print(f"\nDistritos únicos en propiedades ({len(distritos_prop_list)}):")
    for d in sorted(distritos_prop_list):
        print(f"  '{d}'")
    
    # Distritos únicos en requerimientos (nombres)
    distritos_req = Requerimiento.objects.filter(
        distritos__isnull=False
    ).exclude(
        distritos=''
    ).values_list('distritos', flat=True).distinct()
    
    distritos_req_list = list(distritos_req)
    print(f"\nDistritos únicos en requerimientos ({len(distritos_req_list)}):")
    for d in sorted(distritos_req_list)[:50]:  # Mostrar primeros 50
        print(f"  '{d}'")
    
    # Contar cuántos requerimientos tienen cada distrito
    print("\n=== Conteo de Requerimientos por Distrito ===")
    from django.db.models import Count
    distritos_conteo = Requerimiento.objects.filter(
        distritos__isnull=False
    ).exclude(
        distritos=''
    ).values('distritos').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    for item in distritos_conteo:
        print(f"  '{item['distritos']}': {item['count']} requerimientos")
    
    # Verificar si hay algún patrón
    print("\n=== Análisis de Patrones ===")
    
    # Distritos numéricos en propiedades
    distritos_numericos = [d for d in distritos_prop_list if d and d.isdigit()]
    print(f"Distritos numéricos en propiedades: {len(distritos_numericos)}")
    print(f"  Ejemplos: {distritos_numericos[:10]}")
    
    # Distritos que contienen números en requerimientos
    req_con_numeros = []
    for d in distritos_req_list:
        if any(c.isdigit() for c in d):
            req_con_numeros.append(d)
    
    print(f"\nDistritos en requerimientos que contienen números: {len(req_con_numeros)}")
    for d in req_con_numeros[:10]:
        print(f"  '{d}'")
    
    # Buscar posibles mapeos
    print("\n=== Posibles Mapeos ===")
    
    # Mapeo manual basado en conocimiento común de Lima
    mapeo_manual = {
        '1': 'Lima',
        '4': 'Miraflores',
        '23': 'San Isidro',
        # Agregar más según sea necesario
    }
    
    print("Mapeo manual sugerido:")
    for id_distrito, nombre in mapeo_manual.items():
        print(f"  ID '{id_distrito}' -> '{nombre}'")
        
        # Verificar si este nombre existe en requerimientos
        if nombre in distritos_req_list:
            print(f"    ✓ Nombre '{nombre}' existe en requerimientos")
        else:
            # Buscar nombres similares
            similares = [d for d in distritos_req_list if nombre.lower() in d.lower()]
            if similares:
                print(f"    → Nombres similares: {similares[:3]}")
    
    return distritos_prop_list, distritos_req_list

if __name__ == "__main__":
    explorar_distritos()