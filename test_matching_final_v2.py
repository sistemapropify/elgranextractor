#!/usr/bin/env python
"""
Script para verificar el funcionamiento del matching masivo después de los fixes.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from matching.engine import obtener_resumen_matching_masivo
from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty

def test_matching_masivo():
    """Test del matching masivo"""
    print("=== TEST MATCHING MASIVO ===")
    
    # Obtener resumen
    print("Obteniendo resumen de matching masivo...")
    resumen = obtener_resumen_matching_masivo()
    
    print(f"Total de requerimientos procesados: {len(resumen)}")
    
    # Contar requerimientos con match > 0%
    con_match = [r for r in resumen if r['porcentaje_match'] > 0]
    sin_match = [r for r in resumen if r['porcentaje_match'] == 0]
    
    print(f"Requerimientos con match > 0%: {len(con_match)} ({len(con_match)/len(resumen)*100:.1f}%)")
    print(f"Requerimientos con match = 0%: {len(sin_match)} ({len(sin_match)/len(resumen)*100:.1f}%)")
    
    # Contar requerimientos con propiedad match
    con_propiedad_match = [r for r in resumen if r.get('tiene_propiedad_match', False)]
    print(f"Requerimientos con propiedad match: {len(con_propiedad_match)}")
    
    # Mostrar algunos ejemplos con match
    print("\n--- Ejemplos de requerimientos con match ---")
    for i, item in enumerate(con_match[:5]):
        print(f"{i+1}. ID: {item['requerimiento_id']}")
        print(f"   Porcentaje: {item['porcentaje_match']}%")
        print(f"   Tiene propiedad match: {item.get('tiene_propiedad_match', False)}")
        if item.get('tiene_propiedad_match'):
            print(f"   Mejor propiedad: {item.get('mejor_propiedad_codigo')}")
            print(f"   Distrito: {item.get('mejor_propiedad_distrito')}")
            print(f"   Precio: ${item.get('mejor_propiedad_precio')}")
            print(f"   ID Propiedad: {item.get('mejor_propiedad_id')}")
            print(f"   Compatibles: {item.get('total_compatibles')}")
        print()
    
    # Mostrar algunos ejemplos sin match
    print("\n--- Ejemplos de requerimientos sin match ---")
    for i, item in enumerate(sin_match[:3]):
        print(f"{i+1}. ID: {item['requerimiento_id']}")
        print(f"   Porcentaje: {item['porcentaje_match']}%")
        print(f"   Tiene propiedad match: {item.get('tiene_propiedad_match', False)}")
        print()
    
    # Verificar datos de requerimientos problemáticos
    print("\n--- Análisis de requerimientos sin match ---")
    if sin_match:
        req_id = sin_match[0]['requerimiento_id']
        from requerimientos.models import Requerimiento
        try:
            req = Requerimiento.objects.get(id=req_id)
            print(f"Requerimiento ID {req_id}:")
            print(f"  Distritos: '{req.distritos}'")
            print(f"  Presupuesto display: {req.presupuesto_display}")
            print(f"  Tipo propiedad: {req.tipo_propiedad}")
            print(f"  Método pago: {req.metodo_pago}")
            
            # Verificar propiedades disponibles
            propiedades = PropifaiProperty.objects.filter(is_active=True)[:5]
            print(f"  Propiedades activas disponibles (primeras 5): {propiedades.count()}")
            for p in propiedades:
                print(f"    - {p.code}: distrito={p.district}, precio={p.price}")
        except Exception as e:
            print(f"Error al obtener requerimiento: {e}")
    
    # Mostrar estadísticas detalladas
    print("\n--- Estadísticas detalladas ---")
    if con_match:
        porcentajes = [r['porcentaje_match'] for r in con_match]
        print(f"Porcentaje mínimo: {min(porcentajes):.3f}%")
        print(f"Porcentaje máximo: {max(porcentajes):.3f}%")
        print(f"Porcentaje promedio: {sum(porcentajes)/len(porcentajes):.3f}%")
    
    print("\n=== TEST COMPLETADO ===")

if __name__ == '__main__':
    test_matching_masivo()