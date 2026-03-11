#!/usr/bin/env python
"""
Script para probar matching masivo con límite de requerimientos.
"""
import os
import sys
import django
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from requerimientos.models import Requerimiento
from matching.engine import ejecutar_matching_masivo

def probar_masivo_limitado(limite=10):
    """Probar matching masivo con límite de requerimientos."""
    print(f"=== Probando Matching Masivo (limite={limite}) ===")
    
    # Obtener requerimientos limitados
    requerimientos = Requerimiento.objects.order_by('-id')[:limite]
    print(f"Procesando {requerimientos.count()} requerimientos")
    
    # Ejecutar matching masivo
    resultados = ejecutar_matching_masivo(requerimientos=requerimientos, limite_por_requerimiento=5)
    
    # Analizar resultados
    total_requerimientos = len(resultados)
    requerimientos_con_match = 0
    requerimientos_con_match_alto = 0
    
    print("\n=== Resultados ===")
    for req_id, datos in resultados.items():
        mejor_score = datos.get('mejor_score', 0)
        tiene_match = datos.get('tiene_match', False)
        tiene_match_alto = datos.get('tiene_match_alto', False)
        
        if tiene_match:
            requerimientos_con_match += 1
        if tiene_match_alto:
            requerimientos_con_match_alto += 1
        
        print(f"Requerimiento {req_id}:")
        print(f"  Mejor score: {mejor_score:.1f}%")
        print(f"  Tiene match: {tiene_match}")
        print(f"  Match alto (>80%): {tiene_match_alto}")
        if tiene_match_alto:
            print(f"  ⚠️  DEBERÍA MOSTRARSE EN ROJO EN LA INTERFAZ")
    
    print(f"\n=== Resumen ===")
    print(f"Total requerimientos procesados: {total_requerimientos}")
    print(f"Requerimientos con match: {requerimientos_con_match}")
    print(f"Requerimientos con match alto (>80%): {requerimientos_con_match_alto}")
    
    # Verificar si hay algún match alto
    if requerimientos_con_match_alto > 0:
        print("\n✅ Se encontraron requerimientos con match >80%")
        print("   Estos deberían mostrarse en ROJO en la interfaz según lo solicitado por el usuario")
    else:
        print("\n⚠️  No se encontraron requerimientos con match >80%")
        print("   Los scores son bajos debido a:")
        print("   - Discrepancia entre propiedades y requerimientos")
        print("   - Filtros de precio/área/habitaciones muy estrictos")
        print("   - Propiedades no coinciden exactamente con requerimientos")

def crear_requerimiento_de_prueba():
    """Crear un requerimiento de prueba que debería tener match alto."""
    print("\n=== Creando Requerimiento de Prueba con Match Alto ===")
    
    # Buscar una propiedad existente para crear requerimiento que coincida
    from propifai.models import PropifaiProperty
    propiedad_ejemplo = PropifaiProperty.objects.filter(
        is_active=True,
        price__isnull=False,
        district__isnull=False
    ).first()
    
    if not propiedad_ejemplo:
        print("No hay propiedades para crear ejemplo")
        return
    
    print(f"Propiedad ejemplo: ID {propiedad_ejemplo.id}")
    print(f"  Distrito: {propiedad_ejemplo.district}")
    print(f"  Precio: {propiedad_ejemplo.price}")
    print(f"  Habitaciones: {propiedad_ejemplo.bedrooms}")
    print(f"  Baños: {propiedad_ejemplo.bathrooms}")
    
    # Crear un requerimiento que coincida exactamente
    # Nota: No vamos a crear realmente en la base de datos, solo mostramos ejemplo
    print("\nRequerimiento de prueba ideal:")
    print(f"  Distrito: 'Miraflores' (mapea a ID '4')")
    print(f"  Presupuesto: {propiedad_ejemplo.price}")
    print(f"  Habitaciones: {propiedad_ejemplo.bedrooms}")
    print(f"  Baños: {propiedad_ejemplo.bathrooms}")
    print(f"  Área mínima: Cercana al área de la propiedad")
    print("\nEste requerimiento debería tener match cercano al 100%")

if __name__ == "__main__":
    # Probar con pocos requerimientos
    probar_masivo_limitado(5)
    
    # Crear ejemplo de requerimiento con match alto
    crear_requerimiento_de_prueba()
    
    print("\n=== Para ver la interfaz con colores ===")
    print("1. Visitar http://127.0.0.1:8000/matching/masivo/")
    print("2. Los requerimientos con match >80% deberían mostrarse en ROJO")
    print("3. Los requerimientos con match 50-80% en AMARILLO")
    print("4. Los requerimientos con match <50% en VERDE")