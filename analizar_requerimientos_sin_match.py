#!/usr/bin/env python
"""
Analiza por qué la mayoría de requerimientos tienen 0.0% de match.
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
from matching.engine import MatchingEngine

def analizar_requerimientos_sin_match():
    """Analiza una muestra de requerimientos para ver por qué no hacen match."""
    print("=== ANÁLISIS DE REQUERIMIENTOS SIN MATCH ===")
    
    # Tomar una muestra de requerimientos (los primeros 20)
    requerimientos = Requerimiento.objects.all().order_by('-fecha', '-hora')[:20]
    
    # Obtener propiedades activas
    propiedades = PropifaiProperty.objects.filter(is_active=True)[:50]
    print(f"Propiedades activas para evaluación: {propiedades.count()}")
    
    for i, req in enumerate(requerimientos):
        print(f"\n--- Requerimiento {i+1}: ID {req.id} ---")
        print(f"  Distritos: {req.distritos}")
        print(f"  Presupuesto: {req.presupuesto_monto}")
        print(f"  Tipo propiedad: {req.tipo_propiedad}")
        print(f"  Área m2: {req.area_m2}")
        print(f"  Habitaciones: {req.habitaciones}")
        print(f"  Baños: {req.banos}")
        
        # Crear motor de matching
        engine = MatchingEngine(req)
        
        # Evaluar cada propiedad para ver por qué no pasa filtros
        propiedades_evaluadas = 0
        propiedades_descartadas = 0
        razones_descarte = {}
        
        for prop in propiedades:
            propiedades_evaluadas += 1
            
            # Probar filtros discriminatorios
            if not engine._coincide_tipo_propiedad(prop):
                razones_descarte['tipo_propiedad'] = razones_descarte.get('tipo_propiedad', 0) + 1
                continue
            if not engine._coincide_metodo_pago(prop):
                razones_descarte['metodo_pago'] = razones_descarte.get('metodo_pago', 0) + 1
                continue
            if not engine._coincide_distrito(prop):
                razones_descarte['distrito'] = razones_descarte.get('distrito', 0) + 1
                continue
            if not engine._dentro_de_presupuesto(prop):
                razones_descarte['presupuesto'] = razones_descarte.get('presupuesto', 0) + 1
                continue
            
            # Si pasa todos los filtros
            propiedades_descartadas += 1
        
        print(f"  Propiedades evaluadas: {propiedades_evaluadas}")
        print(f"  Propiedades que pasaron filtros: {propiedades_evaluadas - sum(razones_descarte.values())}")
        print(f"  Razones de descarte: {razones_descarte}")
        
        # Si hay propiedades que pasaron filtros, calcular score
        if propiedades_evaluadas - sum(razones_descarte.values()) > 0:
            # Ejecutar matching completo
            resultados = engine.ejecutar_matching(propiedades)
            compatibles = [r for r in resultados if r['fase_eliminada'] is None]
            print(f"  Propiedades compatibles después de scoring: {len(compatibles)}")
            if compatibles:
                mejor = compatibles[0]
                print(f"  Mejor score: {mejor['score_total']:.3f}")
                print(f"  Mejor propiedad: ID {mejor['propiedad'].id}, Código {mejor['propiedad'].code}")
                print(f"    Distrito: {mejor['propiedad'].district}")
                print(f"    Precio: {mejor['propiedad'].price}")
        else:
            print(f"  ❌ Ninguna propiedad pasó los filtros discriminatorios")
            
            # Análisis detallado del primer filtro que falla
            if razones_descarte:
                filtro_principal = max(razones_descarte.items(), key=lambda x: x[1])
                print(f"  Filtro que más descarta: {filtro_principal[0]} ({filtro_principal[1]} propiedades)")
                
                # Mostrar ejemplo de propiedad descartada
                for prop in propiedades:
                    if not engine._coincide_distrito(prop) and filtro_principal[0] == 'distrito':
                        print(f"    Ejemplo: Propiedad {prop.id} tiene distrito '{prop.district}'")
                        print(f"      Requerimiento distritos: {req.distritos}")
                        break
                    if not engine._dentro_de_presupuesto(prop) and filtro_principal[0] == 'presupuesto':
                        print(f"    Ejemplo: Propiedad {prop.id} tiene precio {prop.price}")
                        print(f"      Requerimiento presupuesto: {req.presupuesto_monto}")
                        break

def analizar_datos_requerimientos():
    """Analiza la calidad de los datos de los requerimientos."""
    print("\n=== ANÁLISIS DE CALIDAD DE DATOS DE REQUERIMIENTOS ===")
    
    total = Requerimiento.objects.count()
    print(f"Total requerimientos: {total}")
    
    # Contar requerimientos con datos faltantes
    sin_distritos = Requerimiento.objects.filter(distritos__isnull=True) | Requerimiento.objects.filter(distritos='')
    print(f"Sin distritos: {sin_distritos.count()} ({sin_distritos.count()/total*100:.1f}%)")
    
    sin_presupuesto = Requerimiento.objects.filter(presupuesto_monto__isnull=True)
    print(f"Sin presupuesto: {sin_presupuesto.count()} ({sin_presupuesto.count()/total*100:.1f}%)")
    
    sin_tipo = Requerimiento.objects.filter(tipo_propiedad__isnull=True)
    print(f"Sin tipo propiedad: {sin_tipo.count()} ({sin_tipo.count()/total*100:.1f}%)")
    
    # Requerimientos con datos completos
    completos = Requerimiento.objects.filter(
        distritos__isnull=False,
        distritos__gt='',
        presupuesto_monto__isnull=False,
        tipo_propiedad__isnull=False
    )
    print(f"Con datos completos: {completos.count()} ({completos.count()/total*100:.1f}%)")
    
    # Mostrar algunos ejemplos de distritos comunes
    print("\nDistritos más comunes en requerimientos:")
    from django.db.models import Count
    distritos_comunes = Requerimiento.objects.exclude(distritos__isnull=True).exclude(distritos='').values('distritos').annotate(count=Count('id')).order_by('-count')[:10]
    for d in distritos_comunes:
        print(f"  '{d['distritos']}': {d['count']}")

def probar_requerimiento_especifico(req_id):
    """Prueba un requerimiento específico con detalle."""
    print(f"\n=== PRUEBA DETALLADA PARA REQUERIMIENTO {req_id} ===")
    
    try:
        req = Requerimiento.objects.get(id=req_id)
    except Requerimiento.DoesNotExist:
        print(f"Requerimiento {req_id} no existe")
        return
    
    print(f"Distritos: {req.distritos}")
    print(f"Presupuesto: {req.presupuesto_monto}")
    print(f"Tipo propiedad: {req.tipo_propiedad}")
    print(f"Área m2: {req.area_m2}")
    print(f"Habitaciones: {req.habitaciones}")
    print(f"Baños: {req.banos}")
    
    # Ejecutar matching con todas las propiedades
    from matching.engine import ejecutar_matching_requerimiento
    resultados, estadisticas = ejecutar_matching_requerimiento(req_id)
    
    print(f"\nResultados del matching:")
    print(f"  Total evaluadas: {estadisticas['total_evaluadas']}")
    print(f"  Total compatibles: {estadisticas['total_compatibles']}")
    print(f"  Score promedio: {estadisticas['score_promedio']:.3f}")
    
    if estadisticas['total_compatibles'] > 0:
        print(f"\nTop 3 propiedades match:")
        for i, r in enumerate(resultados[:3]):
            prop = r['propiedad']
            print(f"  {i+1}. Propiedad {prop.id} ({prop.code})")
            print(f"     Score: {r['score_total']:.3f}")
            print(f"     Distrito: {prop.district}")
            print(f"     Precio: {prop.price}")
            print(f"     Área: {prop.built_area}")
            print(f"     Habitaciones: {prop.bedrooms}")
            print(f"     Baños: {prop.bathrooms}")
            
            # Mostrar detalles del scoring
            if 'score_detalle' in r:
                print(f"     Detalle scores:")
                for campo, score in r['score_detalle'].items():
                    if score > 0:
                        print(f"       {campo}: {score:.3f}")
    else:
        print(f"\nNo hay propiedades compatibles.")
        print(f"Descartadas por campo: {estadisticas['descartadas_por_campo']}")

if __name__ == '__main__':
    analizar_datos_requerimientos()
    analizar_requerimientos_sin_match()
    
    # Probar un requerimiento específico que debería tener match
    req_con_match = Requerimiento.objects.filter(distritos__isnull=False).exclude(distritos='').first()
    if req_con_match:
        probar_requerimiento_especifico(req_con_match.id)