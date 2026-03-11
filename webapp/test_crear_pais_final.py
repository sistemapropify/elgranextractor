#!/usr/bin/env python
"""
Script para probar la creación de un país (nivel jerárquico más alto)
sin necesidad de coordenadas.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from cuadrantizacion.models import ZonaValor
from cuadrantizacion.serializers import ZonaValorSerializer
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

def test_crear_pais():
    """Prueba crear un país sin coordenadas."""
    print("=== Prueba de creación de país ===")
    
    # Datos para crear un país
    pais_data = {
        'nombre_zona': 'Perú',
        'descripcion': 'País de Perú',
        'nivel': 'pais',
        'codigo': 'PE',
        'nombre_oficial': 'República del Perú',
        'coordenadas': [],  # Lista vacía
        'activo': True,
        'color_fill': '#FF0000',
        'color_borde': '#CC0000',
        'opacidad': 0.2
    }
    
    # Validar con serializer
    serializer = ZonaValorSerializer(data=pais_data)
    if serializer.is_valid():
        print("OK Serializer válido")
        print(f"  Datos validados: {serializer.validated_data}")
        
        # Intentar crear el objeto
        try:
            zona = serializer.save()
            print(f"OK País creado exitosamente:")
            print(f"  ID: {zona.id}")
            print(f"  Nombre: {zona.nombre_zona}")
            print(f"  Nivel: {zona.nivel}")
            print(f"  Coordenadas: {zona.coordenadas}")
            print(f"  Parent: {zona.parent}")
            
            # Verificar que se puede recuperar
            zona_db = ZonaValor.objects.get(id=zona.id)
            print(f"OK País recuperado de la base de datos")
            
            return zona
        except Exception as e:
            print(f"ERROR Error al guardar: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("ERROR Serializer inválido")
        print(f"  Errores: {serializer.errors}")
    
    return None

def test_crear_jerarquia_completa():
    """Prueba crear una jerarquía completa sin coordenadas para niveles superiores."""
    print("\n=== Prueba de jerarquía completa ===")
    
    # Primero crear el país
    pais = ZonaValor.objects.create(
        nombre_zona='Perú',
        nivel='pais',
        codigo='PE',
        coordenadas=None,  # None también debería funcionar
        activo=True
    )
    print(f"OK País creado: {pais.nombre_zona} (ID: {pais.id})")
    
    # Crear departamento (hijo del país)
    departamento = ZonaValor.objects.create(
        nombre_zona='Lima',
        nivel='departamento',
        codigo='LIM',
        parent=pais,
        coordenadas=None,
        activo=True
    )
    print(f"OK Departamento creado: {departamento.nombre_zona} (Parent: {departamento.parent.nombre_zona})")
    
    # Crear provincia (hijo del departamento)
    provincia = ZonaValor.objects.create(
        nombre_zona='Lima Metropolitana',
        nivel='provincia',
        codigo='LMA',
        parent=departamento,
        coordenadas=None,
        activo=True
    )
    print(f"OK Provincia creada: {provincia.nombre_zona} (Parent: {provincia.parent.nombre_zona})")
    
    # Crear distrito (hijo de la provincia)
    distrito = ZonaValor.objects.create(
        nombre_zona='Miraflores',
        nivel='distrito',
        codigo='MIR',
        parent=provincia,
        coordenadas=None,
        activo=True
    )
    print(f"OK Distrito creado: {distrito.nombre_zona} (Parent: {distrito.parent.nombre_zona})")
    
    # Crear zona (hijo del distrito)
    zona = ZonaValor.objects.create(
        nombre_zona='Zona Central',
        nivel='zona',
        codigo='ZC',
        parent=distrito,
        coordenadas=None,
        activo=True
    )
    print(f"OK Zona creada: {zona.nombre_zona} (Parent: {zona.parent.nombre_zona})")
    
    # Crear subzona CON coordenadas (nivel más básico)
    subzona = ZonaValor.objects.create(
        nombre_zona='Subzona A',
        nivel='subzona',
        codigo='SA',
        parent=zona,
        coordenadas=[[-12.12, -77.03], [-12.11, -77.02], [-12.10, -77.03]],
        activo=True
    )
    print(f"OK Subzona creada: {subzona.nombre_zona} (Parent: {subzona.parent.nombre_zona})")
    print(f"  Coordenadas: {subzona.coordenadas}")
    
    return {
        'pais': pais,
        'departamento': departamento,
        'provincia': provincia,
        'distrito': distrito,
        'zona': zona,
        'subzona': subzona
    }

def test_metodos_jerarquicos(zonas):
    """Prueba los métodos jerárquicos."""
    print("\n=== Prueba de métodos jerárquicos ===")
    
    subzona = zonas['subzona']
    
    # Obtener jerarquía completa
    print(f"Jerarquía de '{subzona.nombre_zona}':")
    current = subzona
    while current:
        print(f"  - {current.nombre_zona} ({current.nivel})")
        current = current.parent
    
    # Obtener path jerárquico
    print(f"\nPath jerárquico: {subzona.get_hierarchy_path()}")
    
    # Obtener display jerárquico
    print(f"Display jerárquico: {subzona.get_hierarchy_display()}")
    
    # Obtener descendientes del país
    pais = zonas['pais']
    descendientes = pais.get_descendants(include_self=True)
    print(f"\nDescendientes de '{pais.nombre_zona}':")
    for d in descendientes:
        print(f"  - {d.nombre_zona} ({d.nivel})")

def limpiar_datos_prueba():
    """Eliminar datos de prueba."""
    print("\n=== Limpiando datos de prueba ===")
    ZonaValor.objects.filter(nombre_zona__in=[
        'Perú', 'Lima', 'Lima Metropolitana', 'Miraflores', 'Zona Central', 'Subzona A'
    ]).delete()
    print("OK Datos de prueba eliminados")

def main():
    """Función principal."""
    print("Iniciando pruebas de creación de país sin coordenadas...")
    
    # Limpiar datos anteriores si existen
    limpiar_datos_prueba()
    
    # Prueba 1: Crear país usando serializer
    pais = test_crear_pais()
    
    if pais:
        # Eliminar para la siguiente prueba
        pais.delete()
    
    # Prueba 2: Crear jerarquía completa
    zonas = test_crear_jerarquia_completa()
    
    # Prueba 3: Probar métodos jerárquicos
    if zonas:
        test_metodos_jerarquicos(zonas)
    
    # Limpiar al final
    limpiar_datos_prueba()
    
    print("\n=== Todas las pruebas completadas ===")

if __name__ == '__main__':
    main()