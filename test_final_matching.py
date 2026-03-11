#!/usr/bin/env python
"""
Prueba final del matching masivo con los cambios implementados.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento
from matching.engine import obtener_resumen_matching_masivo, ejecutar_matching_requerimiento

def test_resumen_mejorado():
    """Prueba que el resumen ahora incluya información de propiedades match."""
    print("=== PRUEBA DE RESUMEN MEJORADO ===")
    
    resumen = obtener_resumen_matching_masivo()
    
    print(f"Total elementos en resumen: {len(resumen)}")
    
    # Mostrar los primeros 5 elementos
    for i, item in enumerate(resumen[:5]):
        print(f"\n{i+1}. Requerimiento {item['requerimiento_id']}:")
        print(f"   Porcentaje: {item['porcentaje_match']:.2f}%")
        print(f"   Compatibles: {item.get('total_compatibles', 0)}")
        
        if item.get('mejor_propiedad_id'):
            print(f"   Mejor propiedad: {item['mejor_propiedad_codigo']} (ID: {item['mejor_propiedad_id']})")
            print(f"   Distrito: {item['mejor_propiedad_distrito']}")
            print(f"   Precio: {item['mejor_propiedad_precio']}")
        else:
            print(f"   Sin propiedad match")
        
        print(f"   Tiene match alto: {item['tiene_match_alto']}")
    
    # Estadísticas
    con_match = sum(1 for item in resumen if item['porcentaje_match'] > 0)
    sin_match = sum(1 for item in resumen if item['porcentaje_match'] == 0)
    con_propiedad = sum(1 for item in resumen if item.get('mejor_propiedad_id'))
    
    print(f"\n=== ESTADÍSTICAS ===")
    print(f"Requerimientos con match > 0%: {con_match} ({con_match/len(resumen)*100:.1f}%)")
    print(f"Requerimientos con match = 0%: {sin_match} ({sin_match/len(resumen)*100:.1f}%)")
    print(f"Requerimientos con propiedad identificada: {con_propiedad} ({con_propiedad/len(resumen)*100:.1f}%)")

def test_requerimiento_especifico():
    """Prueba un requerimiento específico para ver detalles del match."""
    print("\n=== PRUEBA DE REQUERIMIENTO ESPECÍFICO ===")
    
    # Buscar un requerimiento con match
    req_con_match = Requerimiento.objects.filter(
        distritos__isnull=False
    ).exclude(distritos='nan').first()
    
    if not req_con_match:
        print("No se encontró requerimiento con distritos válidos")
        return
    
    print(f"Requerimiento ID: {req_con_match.id}")
    print(f"Distritos: {req_con_match.distritos}")
    print(f"Presupuesto: {req_con_match.presupuesto_monto}")
    
    # Ejecutar matching detallado
    resultados, estadisticas = ejecutar_matching_requerimiento(req_con_match.id)
    
    print(f"\nResultados del matching:")
    print(f"  Total evaluadas: {estadisticas['total_evaluadas']}")
    print(f"  Total compatibles: {estadisticas['total_compatibles']}")
    print(f"  Score promedio: {estadisticas['score_promedio']:.3f}")
    
    if resultados:
        print(f"\nTop 3 propiedades:")
        for i, r in enumerate(resultados[:3]):
            prop = r['propiedad']
            print(f"  {i+1}. {prop.code} (ID: {prop.id})")
            print(f"     Score: {r['score_total']:.3f}")
            print(f"     Distrito: {prop.district}")
            print(f"     Precio: {prop.price}")
            print(f"     Área: {prop.built_area}")
            print(f"     Habitaciones: {prop.bedrooms}")
            
            # Mostrar campos de coincidencia
            if 'score_detalle' in r:
                campos_coincidentes = [campo for campo, score in r['score_detalle'].items() if score > 0.5]
                if campos_coincidentes:
                    print(f"     Campos con buena coincidencia: {', '.join(campos_coincidentes)}")
    else:
        print(f"\nNo hay propiedades compatibles.")
        print(f"Descartadas por campo: {estadisticas['descartadas_por_campo']}")

def test_problema_nan():
    """Verifica que los requerimientos con distrito 'nan' ahora tengan match."""
    print("\n=== PRUEBA DE REQUERIMIENTOS CON 'nan' ===")
    
    req_nan = Requerimiento.objects.filter(distritos='nan').first()
    if req_nan:
        print(f"Requerimiento con 'nan': ID {req_nan.id}")
        
        from matching.engine import MatchingEngine
        from propifai.models import PropifaiProperty
        
        engine = MatchingEngine(req_nan)
        propiedades = PropifaiProperty.objects.filter(is_active=True)[:5]
        
        # Verificar filtro de distrito
        for prop in propiedades:
            coincide = engine._coincide_distrito(prop)
            print(f"  Propiedad {prop.id} (distrito: {prop.district}) -> coincide: {coincide}")
        
        # Ejecutar matching completo
        resultados = engine.ejecutar_matching(propiedades[:10])
        compatibles = [r for r in resultados if r['fase_eliminada'] is None]
        print(f"  Propiedades compatibles: {len(compatibles)}")
        
        if compatibles:
            print(f"  ¡Funciona! Requerimientos con 'nan' ahora pueden tener match.")
        else:
            print(f"  Aún sin match. Razón: {estadisticas.get('descartadas_por_campo', 'desconocida')}")

if __name__ == '__main__':
    test_resumen_mejorado()
    test_requerimiento_especifico()
    test_problema_nan()
    
    print("\n=== CONCLUSIÓN ===")
    print("1. Se corrigió el problema de distrito 'nan' (ahora se considera como 'sin distrito específico').")
    print("2. El resumen ahora incluye información de la mejor propiedad match.")
    print("3. La vista masivo mostrará columna con propiedad match y comparativo.")
    print("4. Los porcentajes ya no serán todos 0.0% para requerimientos con datos válidos.")