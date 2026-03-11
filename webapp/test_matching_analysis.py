#!/usr/bin/env python
"""
Script para analizar por qué el matching está dando 0% de coincidencia.
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

def analizar_requerimiento(requerimiento_id):
    """Analizar un requerimiento específico y sus propiedades compatibles."""
    try:
        requerimiento = Requerimiento.objects.get(id=requerimiento_id)
        print(f"\n=== Análisis del Requerimiento ID: {requerimiento_id} ===")
        print(f"Tipo propiedad: {requerimiento.tipo_propiedad}")
        print(f"Método pago: {requerimiento.metodo_pago}")
        print(f"Distrito: {requerimiento.distrito}")
        print(f"Presupuesto: {requerimiento.presupuesto}")
        print(f"Área mínima: {requerimiento.area_minima}")
        print(f"Habitaciones: {requerimiento.habitaciones}")
        print(f"Baños: {requerimiento.banos}")
        
        # Crear motor de matching
        engine = MatchingEngine(requerimiento)
        
        # Obtener todas las propiedades activas
        propiedades = PropifaiProperty.objects.filter(is_active=True)
        print(f"\nTotal propiedades activas: {propiedades.count()}")
        
        # Probar filtros discriminatorios en las primeras 10 propiedades
        print("\n--- Evaluando filtros discriminatorios ---")
        compatibles = 0
        descartadas = 0
        
        for i, propiedad in enumerate(propiedades[:20]):  # Solo primeras 20 para análisis
            razon = engine._aplicar_filtros_discriminatorios(propiedad)
            if razon is None:
                compatibles += 1
                print(f"  Propiedad {propiedad.id}: COMPATIBLE")
                print(f"    - Tipo: {propiedad.property_type}")
                print(f"    - Distrito: {propiedad.district}")
                print(f"    - Precio: {propiedad.price}")
                print(f"    - Método: {propiedad.transaction_type}")
            else:
                descartadas += 1
                if i < 5:  # Mostrar solo primeras 5 descartadas
                    print(f"  Propiedad {propiedad.id}: DESCARTADA - {razon}")
        
        print(f"\nResumen: {compatibles} compatibles, {descartadas} descartadas (de {min(20, propiedades.count())} evaluadas)")
        
        # Si hay compatibles, calcular scoring
        if compatibles > 0:
            print("\n--- Calculando scoring para propiedades compatibles ---")
            resultados = engine.ejecutar_matching(propiedades[:10])
            for i, resultado in enumerate(resultados[:5]):
                print(f"  Propiedad {resultado['propiedad'].id}: Score {resultado['score_final']:.1f}%")
                print(f"    - Razones eliminación: {resultado.get('razon_eliminacion', 'Ninguna')}")
                print(f"    - Desglose: {resultado.get('desglose_scores', {})}")
        
        return compatibles
        
    except Requerimiento.DoesNotExist:
        print(f"Requerimiento {requerimiento_id} no encontrado")
        return 0

def analizar_propiedades():
    """Analizar estadísticas generales de propiedades."""
    print("\n=== Análisis de Propiedades ===")
    
    total = PropifaiProperty.objects.count()
    activas = PropifaiProperty.objects.filter(is_active=True).count()
    
    print(f"Total propiedades: {total}")
    print(f"Propiedades activas: {activas}")
    
    # Distribución por tipo
    tipos = PropifaiProperty.objects.values('property_type').annotate(count=models.Count('id'))
    print("\nDistribución por tipo de propiedad:")
    for tipo in tipos[:10]:
        print(f"  {tipo['property_type']}: {tipo['count']}")
    
    # Distribución por distrito
    distritos = PropifaiProperty.objects.values('district').annotate(count=models.Count('id'))
    print("\nDistribución por distrito (top 10):")
    for distrito in distritos[:10]:
        print(f"  {distrito['district']}: {distrito['count']}")
    
    # Rango de precios
    from django.db.models import Min, Max
    precios = PropifaiProperty.objects.aggregate(
        min_precio=Min('price'),
        max_precio=Max('price'),
        avg_precio=models.Avg('price')
    )
    print(f"\nRango de precios:")
    print(f"  Mínimo: {precios['min_precio']}")
    print(f"  Máximo: {precios['max_precio']}")
    print(f"  Promedio: {precios['avg_precio']:.2f}")

def analizar_requerimientos():
    """Analizar estadísticas de requerimientos."""
    print("\n=== Análisis de Requerimientos ===")
    
    total = Requerimiento.objects.count()
    print(f"Total requerimientos: {total}")
    
    # Distribución por tipo
    tipos = Requerimiento.objects.values('tipo_propiedad').annotate(count=models.Count('id'))
    print("\nDistribución por tipo de propiedad:")
    for tipo in tipos:
        print(f"  {tipo['tipo_propiedad']}: {tipo['count']}")
    
    # Distribución por distrito
    distritos = Requerimiento.objects.values('distrito').annotate(count=models.Count('id'))
    print("\nDistribución por distrito (top 10):")
    for distrito in distritos[:10]:
        print(f"  {distrito['distrito']}: {distrito['count']}")
    
    # Rango de presupuestos
    from django.db.models import Min, Max
    presupuestos = Requerimiento.objects.aggregate(
        min_presupuesto=Min('presupuesto'),
        max_presupuesto=Max('presupuesto'),
        avg_presupuesto=models.Avg('presupuesto')
    )
    print(f"\nRango de presupuestos:")
    print(f"  Mínimo: {presupuestos['min_presupuesto']}")
    print(f"  Máximo: {presupuestos['max_presupuesto']}")
    print(f"  Promedio: {presupuestos['avg_presupuesto']:.2f}")

if __name__ == "__main__":
    from django.db import models
    
    print("=== ANÁLISIS DE MATCHING CERO ===")
    
    # Analizar propiedades y requerimientos
    analizar_propiedades()
    analizar_requerimientos()
    
    # Analizar algunos requerimientos específicos
    print("\n=== Analizando requerimientos específicos ===")
    
    # Tomar algunos requerimientos recientes
    requerimientos_recientes = Requerimiento.objects.order_by('-id')[:5]
    
    for req in requerimientos_recientes:
        print(f"\nAnalizando requerimiento ID: {req.id}")
        compatibles = analizar_requerimiento(req.id)
        
        if compatibles == 0:
            print(f"  ⚠️  Requerimiento {req.id} tiene 0 propiedades compatibles")
            print(f"  Posibles causas:")
            print(f"  - Tipo propiedad: {req.tipo_propiedad}")
            print(f"  - Distrito: {req.distrito}")
            print(f"  - Presupuesto: {req.presupuesto}")
        else:
            print(f"  ✅ Requerimiento {req.id} tiene {compatibles} propiedades compatibles")
    
    print("\n=== Análisis completado ===")