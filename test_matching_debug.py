#!/usr/bin/env python
"""
Script para debuggear el matching masivo.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty
from matching.engine import ejecutar_matching_requerimiento, MatchingEngine

def test_matching_simple():
    """Prueba el matching para un requerimiento específico."""
    print("=== PRUEBA DE MATCHING SIMPLE ===")
    
    # Obtener un requerimiento con datos
    req = Requerimiento.objects.filter(distritos__isnull=False).exclude(distritos='').first()
    if not req:
        req = Requerimiento.objects.first()
    
    print(f"Requerimiento ID: {req.id}")
    print(f"  Distritos: {req.distritos}")
    print(f"  Presupuesto: {req.presupuesto_monto}")
    print(f"  Tipo propiedad: {req.tipo_propiedad}")
    print(f"  Área m2: {req.area_m2}")
    print(f"  Habitaciones: {req.habitaciones}")
    
    # Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.all()[:10]
    print(f"\nPropiedades a evaluar: {propiedades.count()}")
    
    for i, prop in enumerate(propiedades):
        print(f"\nPropiedad {i+1}: ID={prop.id}, Código={prop.code}")
        print(f"  Distrito: {prop.district}")
        print(f"  Precio: {prop.price}")
        print(f"  Área construida: {prop.built_area}")
        print(f"  Habitaciones: {prop.bedrooms}")
        print(f"  Baños: {prop.bathrooms}")
    
    # Ejecutar matching
    print("\n--- Ejecutando matching ---")
    try:
        resultados, estadisticas = ejecutar_matching_requerimiento(req.id, propiedades=propiedades)
        
        print(f"Total evaluadas: {estadisticas['total_evaluadas']}")
        print(f"Total descartadas: {estadisticas['total_descartadas']}")
        print(f"Total compatibles: {estadisticas['total_compatibles']}")
        print(f"Descartadas por campo: {estadisticas['descartadas_por_campo']}")
        print(f"Score promedio: {estadisticas['score_promedio']}")
        
        if resultados:
            print("\nResultados compatibles (top 5):")
            for i, r in enumerate(resultados[:5]):
                prop = r['propiedad']
                print(f"  {i+1}. Propiedad {prop.id} ({prop.code})")
                print(f"     Score: {r['score_total']:.2f}")
                print(f"     Distrito: {prop.district}")
                print(f"     Precio: {prop.price}")
        else:
            print("\nNo hay propiedades compatibles.")
            
    except Exception as e:
        print(f"Error al ejecutar matching: {e}")
        import traceback
        traceback.print_exc()

def test_filtros_discriminatorios():
    """Prueba los filtros discriminatorios directamente."""
    print("\n=== PRUEBA DE FILTROS DISCRIMINATORIOS ===")
    
    req = Requerimiento.objects.filter(distritos__isnull=False).exclude(distritos='').first()
    if not req:
        print("No hay requerimientos con distritos")
        return
    
    engine = MatchingEngine(req)
    
    propiedades = PropifaiProperty.objects.all()[:5]
    
    for prop in propiedades:
        print(f"\nPropiedad ID {prop.id} ({prop.code}):")
        print(f"  Distrito: {prop.district}")
        print(f"  Precio: {prop.price}")
        
        # Probar cada filtro
        tipo_ok = engine._coincide_tipo_propiedad(prop)
        metodo_ok = engine._coincide_metodo_pago(prop)
        distrito_ok = engine._coincide_distrito(prop)
        presupuesto_ok = engine._dentro_de_presupuesto(prop)
        
        print(f"  Tipo propiedad OK: {tipo_ok}")
        print(f"  Método pago OK: {metodo_ok}")
        print(f"  Distrito OK: {distrito_ok}")
        print(f"  Presupuesto OK: {presupuesto_ok}")
        
        if all([tipo_ok, metodo_ok, distrito_ok, presupuesto_ok]):
            print("  -> PASA todos los filtros")
        else:
            print("  -> DESCARTA por algún filtro")

def test_matching_masivo():
    """Prueba la función de matching masivo."""
    print("\n=== PRUEBA DE MATCHING MASIVO ===")
    
    from matching.engine import ejecutar_matching_masivo, obtener_resumen_matching_masivo
    
    # Probar obtener_resumen_matching_masivo
    print("1. Obteniendo resumen de matching masivo...")
    resumen = obtener_resumen_matching_masivo()
    print(f"   Elementos en resumen: {len(resumen)}")
    
    if resumen:
        for i, item in enumerate(resumen[:3]):
            print(f"   {i+1}. Requerimiento {item['requerimiento_id']}: {item['porcentaje_match']:.1f}%")
    
    # Probar ejecutar_matching_masivo (limitado)
    print("\n2. Ejecutando matching masivo (limitado a 3 requerimientos)...")
    requerimientos = Requerimiento.objects.all()[:3]
    resultados = ejecutar_matching_masivo(requerimientos=requerimientos, limite_por_requerimiento=5)
    
    print(f"   Requerimientos procesados: {len(resultados)}")
    for req_id, datos in resultados.items():
        print(f"   Requerimiento {req_id}:")
        print(f"     Mejor score: {datos['mejor_score']:.2f}")
        print(f"     Compatibles: {datos['total_compatibles']}")
        print(f"     Tiene match alto: {datos['tiene_match_alto']}")

if __name__ == '__main__':
    test_matching_simple()
    test_filtros_discriminatorios()
    test_matching_masivo()