#!/usr/bin/env python
"""
Script para analizar por qué el matching está dando 0% de coincidencia.
Versión corregida con nombres de campo correctos y análisis de distritos.
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

def analizar_datos_basicos():
    """Analizar datos básicos de propiedades y requerimientos."""
    print("\n=== Datos Básicos del Sistema ===")
    
    # Propiedades
    total_prop = PropifaiProperty.objects.count()
    activas_prop = PropifaiProperty.objects.filter(is_active=True).count()
    
    print(f"\nPropiedades:")
    print(f"  Total: {total_prop}")
    print(f"  Activas: {activas_prop}")
    
    # Mostrar algunas propiedades con más detalles
    print("\nPrimeras 5 propiedades activas (detalles):")
    for prop in PropifaiProperty.objects.filter(is_active=True)[:5]:
        print(f"  ID: {prop.id}")
        print(f"    - Distrito: '{prop.district}' (tipo: {type(prop.district)})")
        print(f"    - Precio: {prop.price}")
        print(f"    - Habitaciones: {prop.bedrooms}")
        print(f"    - Baños: {prop.bathrooms}")
        print(f"    - Área construida: {prop.built_area}")
    
    # Requerimientos
    total_req = Requerimiento.objects.count()
    
    print(f"\nRequerimientos:")
    print(f"  Total: {total_req}")
    
    # Mostrar algunos requerimientos
    print("\nPrimeros 5 requerimientos:")
    for req in Requerimiento.objects.all()[:5]:
        print(f"  ID: {req.id}")
        print(f"    - Distritos: '{req.distritos}'")
        print(f"    - Presupuesto: {req.presupuesto}")
        print(f"    - Tipo propiedad: {req.tipo_propiedad}")
        print(f"    - Método pago: {req.metodo_pago}")
        print(f"    - Área mínima: {req.area_minima}")
    
    # Verificar campos de distrito más detalladamente
    print("\n--- Análisis Detallado de Distritos ---")
    
    # Distritos únicos en propiedades
    distritos_prop = PropifaiProperty.objects.filter(district__isnull=False).exclude(district='').values_list('district', flat=True).distinct()
    distritos_prop_list = list(distritos_prop)
    print(f"Distritos únicos en propiedades ({len(distritos_prop_list)}):")
    for d in distritos_prop_list[:15]:
        print(f"  '{d}'")
    
    # Distritos únicos en requerimientos
    distritos_req = Requerimiento.objects.filter(distritos__isnull=False).exclude(distritos='').values_list('distritos', flat=True).distinct()
    distritos_req_list = list(distritos_req)
    print(f"\nDistritos únicos en requerimientos ({len(distritos_req_list)}):")
    for d in distritos_req_list[:15]:
        print(f"  '{d}'")
    
    # Analizar formato de distritos en propiedades
    print("\n--- Formato de Distritos en Propiedades ---")
    distritos_numericos = [d for d in distritos_prop_list if d and d.isdigit()]
    distritos_texto = [d for d in distritos_prop_list if d and not d.isdigit()]
    
    print(f"Distritos numéricos (IDs): {len(distritos_numericos)}")
    print(f"Distritos en texto: {len(distritos_texto)}")
    
    if distritos_texto:
        print(f"  Ejemplos texto: {distritos_texto[:5]}")
    
    # Verificar si hay requerimientos con distritos numéricos
    print("\n--- Requerimientos con Distritos Numéricos ---")
    req_con_numeros = []
    for req in Requerimiento.objects.filter(distritos__isnull=False).exclude(distritos='')[:20]:
        if any(c.isdigit() for c in req.distritos):
            req_con_numeros.append(req)
    
    print(f"Requerimientos con dígitos en distritos: {len(req_con_numeros)}")
    for req in req_con_numeros[:5]:
        print(f"  ID {req.id}: '{req.distritos}'")
    
    return distritos_prop_list, distritos_req_list

def analizar_matching_simple(requerimiento_id):
    """Analizar matching simple para un requerimiento."""
    try:
        req = Requerimiento.objects.get(id=requerimiento_id)
        print(f"\n=== Matching Simple para Requerimiento {requerimiento_id} ===")
        print(f"Distritos: '{req.distritos}'")
        print(f"Distritos lista: {req.distritos_lista}")
        print(f"Presupuesto: {req.presupuesto}")
        
        # Crear motor
        engine = MatchingEngine(req)
        
        # Probar con una propiedad
        propiedades = PropifaiProperty.objects.filter(is_active=True)[:3]
        
        for prop in propiedades:
            print(f"\nPropiedad {prop.id}:")
            print(f"  Distrito: '{prop.district}'")
            print(f"  Precio: {prop.price}")
            
            # Verificar distrito
            distrito_ok = engine._coincide_distrito(prop)
            print(f"  Distrito OK: {distrito_ok}")
            
            # Verificar presupuesto
            presupuesto_ok = engine._dentro_de_presupuesto(prop)
            print(f"  Presupuesto OK: {presupuesto_ok}")
            
            # Filtro completo
            razon = engine._aplicar_filtros_discriminatorios(prop)
            print(f"  Filtro completo: {'PASÓ' if razon is None else f'FALLÓ ({razon})'}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def probar_matching_con_distrito_especifico():
    """Probar matching con un requerimiento que tenga distrito específico."""
    print("\n=== Probando Matching con Distrito Específico ===")
    
    # Buscar un requerimiento con distrito no vacío
    req_con_distrito = Requerimiento.objects.filter(distritos__isnull=False).exclude(distritos='').first()
    
    if not req_con_distrito:
        print("No hay requerimientos con distritos especificados")
        return
    
    print(f"Usando requerimiento ID: {req_con_distrito.id}")
    print(f"Distritos: '{req_con_distrito.distritos}'")
    
    # Crear motor
    engine = MatchingEngine(req_con_distrito)
    
    # Probar con todas las propiedades
    propiedades = PropifaiProperty.objects.filter(is_active=True)
    
    compatibles_distrito = 0
    compatibles_presupuesto = 0
    compatibles_totales = 0
    
    for prop in propiedades:
        distrito_ok = engine._coincide_distrito(prop)
        presupuesto_ok = engine._dentro_de_presupuesto(prop)
        
        if distrito_ok:
            compatibles_distrito += 1
        if presupuesto_ok:
            compatibles_presupuesto += 1
        
        razon = engine._aplicar_filtros_discriminatorios(prop)
        if razon is None:
            compatibles_totales += 1
    
    print(f"\nResultados:")
    print(f"  Propiedades totales: {propiedades.count()}")
    print(f"  Compatibles por distrito: {compatibles_distrito}")
    print(f"  Compatibles por presupuesto: {compatibles_presupuesto}")
    print(f"  Compatibles totales (todos filtros): {compatibles_totales}")
    
    # Si hay compatibles, mostrar detalles
    if compatibles_totales > 0:
        print("\nPropiedades compatibles:")
        for prop in propiedades:
            razon = engine._aplicar_filtros_discriminatorios(prop)
            if razon is None:
                print(f"  ID {prop.id}: Distrito '{prop.district}', Precio {prop.price}")

if __name__ == "__main__":
    print("=== ANÁLISIS DE MATCHING CERO - ANÁLISIS DE DISTRITOS ===")
    
    # Analizar datos básicos
    distritos_prop, distritos_req = analizar_datos_basicos()
    
    # Probar matching con distrito específico
    probar_matching_con_distrito_especifico()
    
    # Analizar algunos requerimientos específicos
    print("\n=== Analizando Requerimientos Específicos ===")
    
    # Tomar algunos requerimientos recientes
    requerimientos_recientes = Requerimiento.objects.order_by('-id')[:3]
    
    for req in requerimientos_recientes:
        analizar_matching_simple(req.id)
    
    print("\n=== Conclusiones ===")
    print("1. Los distritos en propiedades parecen ser IDs numéricos (ej: '4', '23')")
    print("2. Los distritos en requerimientos parecen ser nombres de texto")
    print("3. Esto causa que _coincide_distrito() siempre retorne False")
    print("4. Solución: Necesitamos un mapeo entre IDs de distrito y nombres")
    print("5. Alternativa: Modificar la lógica para manejar ambos formatos")