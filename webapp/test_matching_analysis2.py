#!/usr/bin/env python
"""
Script para analizar por qué el matching está dando 0% de coincidencia.
Versión corregida con nombres de campo correctos.
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
from django.db import models

def analizar_requerimiento_detallado(requerimiento_id):
    """Analizar un requerimiento específico con más detalle."""
    try:
        requerimiento = Requerimiento.objects.get(id=requerimiento_id)
        print(f"\n=== Análisis Detallado del Requerimiento ID: {requerimiento_id} ===")
        print(f"Tipo propiedad: {requerimiento.tipo_propiedad}")
        print(f"Método pago: {requerimiento.metodo_pago}")
        print(f"Distrito: {requerimiento.distrito}")
        print(f"Distritos lista: {requerimiento.distritos_lista}")
        print(f"Presupuesto: {requerimiento.presupuesto}")
        print(f"Presupuesto monto: {requerimiento.presupuesto_monto}")
        print(f"Área mínima: {requerimiento.area_minima}")
        print(f"Habitaciones: {requerimiento.habitaciones}")
        print(f"Baños: {requerimiento.banos}")
        
        # Crear motor de matching
        engine = MatchingEngine(requerimiento)
        
        # Obtener todas las propiedades activas
        propiedades = PropifaiProperty.objects.filter(is_active=True)
        print(f"\nTotal propiedades activas: {propiedades.count()}")
        
        # Analizar cada filtro por separado
        print("\n--- Análisis de Filtros Discriminatorios ---")
        
        for i, propiedad in enumerate(propiedades[:10]):  # Solo primeras 10 para análisis
            print(f"\nPropiedad {propiedad.id}:")
            print(f"  - Distrito: {propiedad.district}")
            print(f"  - Precio: {propiedad.price}")
            print(f"  - Tipo (propiedad.tipo_propiedad): {propiedad.tipo_propiedad}")
            
            # Verificar cada filtro individualmente
            # 1. Tipo de propiedad
            tipo_ok = engine._coincide_tipo_propiedad(propiedad)
            print(f"  - Tipo OK: {tipo_ok}")
            
            # 2. Método de pago
            metodo_ok = engine._coincide_metodo_pago(propiedad)
            print(f"  - Método OK: {metodo_ok}")
            
            # 3. Distrito
            distrito_ok = engine._coincide_distrito(propiedad)
            print(f"  - Distrito OK: {distrito_ok}")
            if not distrito_ok:
                print(f"    Requerimiento distritos: {requerimiento.distritos_lista}")
                print(f"    Propiedad distrito: {propiedad.district}")
            
            # 4. Presupuesto
            presupuesto_ok = engine._dentro_de_presupuesto(propiedad)
            print(f"  - Presupuesto OK: {presupuesto_ok}")
            if not presupuesto_ok:
                print(f"    Requerimiento presupuesto: {requerimiento.presupuesto_monto}")
                print(f"    Propiedad precio: {propiedad.price}")
            
            # Filtro completo
            razon = engine._aplicar_filtros_discriminatorios(propiedad)
            print(f"  - Filtro completo: {'PASÓ' if razon is None else f'FALLÓ ({razon})'}")
        
        # Ejecutar matching completo para ver scoring
        print("\n--- Ejecutando Matching Completo ---")
        resultados = engine.ejecutar_matching(propiedades[:5])
        
        if resultados:
            print(f"Encontrados {len(resultados)} propiedades compatibles:")
            for resultado in resultados:
                print(f"  Propiedad {resultado['propiedad'].id}: Score {resultado['score_total']:.1f}%")
                if resultado.get('razon_eliminacion'):
                    print(f"    Razón eliminación: {resultado['razon_eliminacion']}")
        else:
            print("No se encontraron propiedades compatibles")
            
        return len(resultados)
        
    except Requerimiento.DoesNotExist:
        print(f"Requerimiento {requerimiento_id} no encontrado")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 0

def analizar_datos_basicos():
    """Analizar datos básicos de propiedades y requerimientos."""
    print("\n=== Datos Básicos del Sistema ===")
    
    # Propiedades
    total_prop = PropifaiProperty.objects.count()
    activas_prop = PropifaiProperty.objects.filter(is_active=True).count()
    
    print(f"\nPropiedades:")
    print(f"  Total: {total_prop}")
    print(f"  Activas: {activas_prop}")
    
    # Mostrar algunas propiedades
    print("\nPrimeras 5 propiedades activas:")
    for prop in PropifaiProperty.objects.filter(is_active=True)[:5]:
        print(f"  ID: {prop.id}, Distrito: {prop.district}, Precio: {prop.price}, Habitaciones: {prop.bedrooms}")
    
    # Requerimientos
    total_req = Requerimiento.objects.count()
    
    print(f"\nRequerimientos:")
    print(f"  Total: {total_req}")
    
    # Mostrar algunos requerimientos
    print("\nPrimeros 5 requerimientos:")
    for req in Requerimiento.objects.all()[:5]:
        print(f"  ID: {req.id}, Distrito: {req.distrito}, Presupuesto: {req.presupuesto}, Tipo: {req.tipo_propiedad}")
    
    # Verificar campos de distrito
    print("\n--- Análisis de Campos Distrito ---")
    
    # Distritos únicos en propiedades
    distritos_prop = PropifaiProperty.objects.filter(district__isnull=False).values_list('district', flat=True).distinct()
    print(f"Distritos únicos en propiedades: {list(distritos_prop)[:10]}...")
    
    # Distritos únicos en requerimientos
    distritos_req = Requerimiento.objects.filter(distrito__isnull=False).values_list('distrito', flat=True).distinct()
    print(f"Distritos únicos en requerimientos: {list(distritos_req)[:10]}...")
    
    # Verificar si hay superposición
    distritos_prop_set = set(d.lower().strip() for d in distritos_prop if d)
    distritos_req_set = set(d.lower().strip() for d in distritos_req if d)
    
    superposicion = distritos_prop_set.intersection(distritos_req_set)
    print(f"\nDistritos en común: {len(superposicion)}")
    if superposicion:
        print(f"  Ejemplos: {list(superposicion)[:5]}")
    else:
        print("  ⚠️  No hay distritos en común entre propiedades y requerimientos")
        
        # Mostrar algunos ejemplos de cada lado
        print(f"  Ejemplo distritos propiedades: {list(distritos_prop_set)[:5]}")
        print(f"  Ejemplo distritos requerimientos: {list(distritos_req_set)[:5]}")

if __name__ == "__main__":
    print("=== ANÁLISIS DE MATCHING CERO - VERSIÓN CORREGIDA ===")
    
    # Analizar datos básicos
    analizar_datos_basicos()
    
    # Analizar algunos requerimientos específicos
    print("\n=== Analizando requerimientos específicos ===")
    
    # Tomar algunos requerimientos recientes
    requerimientos_recientes = Requerimiento.objects.order_by('-id')[:3]
    
    for req in requerimientos_recientes:
        print(f"\n{'='*60}")
        compatibles = analizar_requerimiento_detallado(req.id)
        
        if compatibles == 0:
            print(f"\n⚠️  Requerimiento {req.id} tiene 0 propiedades compatibles")
        else:
            print(f"\n✅ Requerimiento {req.id} tiene {compatibles} propiedades compatibles")
    
    print("\n=== Análisis completado ===")