#!/usr/bin/env python
"""
Script para probar el matching con la corrección de distritos.
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
from matching.engine import MatchingEngine

def probar_matching_individual(requerimiento_id):
    """Probar matching para un requerimiento específico."""
    try:
        req = Requerimiento.objects.get(id=requerimiento_id)
        print(f"\n=== Probando Matching para Requerimiento {requerimiento_id} ===")
        print(f"Distritos: '{req.distritos}'")
        print(f"Distritos lista: {req.distritos_lista}")
        
        # Crear motor
        engine = MatchingEngine(req)
        
        # Obtener propiedades activas
        propiedades = PropifaiProperty.objects.filter(is_active=True)
        print(f"Propiedades activas: {propiedades.count()}")
        
        # Probar filtros discriminatorios
        compatibles = 0
        for prop in propiedades[:10]:  # Probar con primeras 10
            razon = engine._aplicar_filtros_discriminatorios(prop)
            if razon is None:
                compatibles += 1
                print(f"  Propiedad {prop.id}: COMPATIBLE (Distrito: '{prop.district}', Precio: {prop.price})")
            else:
                print(f"  Propiedad {prop.id}: DESCARTADA - {razon}")
        
        print(f"\nCompatibles encontrados: {compatibles} de {min(10, propiedades.count())}")
        
        # Ejecutar matching completo si hay compatibles
        if compatibles > 0:
            print("\n--- Ejecutando Matching Completo ---")
            resultados = engine.ejecutar_matching(propiedades[:20])
            
            if resultados:
                print(f"Resultados del matching: {len(resultados)} propiedades")
                for i, resultado in enumerate(resultados[:5]):
                    print(f"  {i+1}. Propiedad {resultado['propiedad'].id}: Score {resultado['score_total']:.1f}%")
                    if resultado['score_total'] > 80:
                        print(f"     ⚠️  ALTO MATCH (>80%) - Debería mostrarse en ROJO")
            else:
                print("No se encontraron propiedades compatibles después del scoring")
        
        return compatibles
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 0

def probar_matching_masivo_rapido():
    """Probar matching masivo rápido con algunos requerimientos."""
    print("\n=== Probando Matching Masivo Rápido ===")
    
    # Tomar 5 requerimientos recientes
    requerimientos = Requerimiento.objects.order_by('-id')[:5]
    
    total_compatibles = 0
    for req in requerimientos:
        print(f"\nRequerimiento {req.id}: '{req.distritos}'")
        
        engine = MatchingEngine(req)
        propiedades = PropifaiProperty.objects.filter(is_active=True)[:5]  # Solo 5 propiedades
        
        compatibles = 0
        for prop in propiedades:
            razon = engine._aplicar_filtros_discriminatorios(prop)
            if razon is None:
                compatibles += 1
        
        print(f"  Compatibles: {compatibles} de {propiedades.count()}")
        total_compatibles += compatibles
        
        # Si hay compatibles, calcular score
        if compatibles > 0:
            resultados = engine.ejecutar_matching(propiedades)
            if resultados:
                mejor_score = max(r['score_total'] for r in resultados)
                print(f"  Mejor score: {mejor_score:.1f}%")
                if mejor_score > 80:
                    print(f"  ⚠️  REQUERIMIENTO CON MATCH ALTO (>80%)")
    
    print(f"\nTotal compatibles encontrados: {total_compatibles}")

def verificar_mapeo_distritos():
    """Verificar el mapeo de distritos implementado."""
    print("\n=== Verificando Mapeo de Distritos ===")
    
    # IDs de distrito en propiedades
    ids_distritos = ['1', '2', '3', '4', '7', '8', '13', '18', '23', '25', '27']
    
    # Mapeo implementado
    mapeo = {
        '1': 'cercado',
        '2': 'yanahuara',
        '3': 'cayma',
        '4': 'miraflores',
        '7': 'cerro colorado',
        '8': 'sachaca',
        '13': 'socabaya',
        '18': 'umacollo',
        '23': 'vallecito',
        '25': 'bustamante',
        '27': 'yanahuara',
    }
    
    print("Mapeo implementado:")
    for id_distrito, nombre in mapeo.items():
        print(f"  ID '{id_distrito}' -> '{nombre}'")
    
    # Verificar si estos nombres aparecen en requerimientos
    print("\nDistritos comunes en requerimientos:")
    from django.db.models import Count
    distritos_comunes = Requerimiento.objects.exclude(
        distritos__isnull=True
    ).exclude(
        distritos=''
    ).values('distritos').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    for item in distritos_comunes:
        distrito = item['distritos'].lower()
        print(f"  '{distrito}': {item['count']} requerimientos")

if __name__ == "__main__":
    print("=== PRUEBA DE MATCHING CON CORRECCIÓN DE DISTRITOS ===")
    
    # Verificar mapeo
    verificar_mapeo_distritos()
    
    # Probar con algunos requerimientos específicos
    print("\n=== Pruebas Individuales ===")
    
    # Probar con un requerimiento que tenga 'Miraflores' (debería mapear con ID '4')
    req_miraflores = Requerimiento.objects.filter(
        distritos__icontains='Miraflores'
    ).first()
    
    if req_miraflores:
        probar_matching_individual(req_miraflores.id)
    else:
        print("No se encontró requerimiento con 'Miraflores'")
    
    # Probar con un requerimiento que tenga 'nan' (debería aceptar todas)
    req_nan = Requerimiento.objects.filter(
        distritos__isnull=True
    ).first()
    
    if req_nan:
        probar_matching_individual(req_nan.id)
    
    # Probar matching masivo rápido
    probar_matching_masivo_rapido()
    
    print("\n=== Prueba completada ===")