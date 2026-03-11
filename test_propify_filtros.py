#!/usr/bin/env python
"""
Script para probar los filtros de propiedades Propify.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from propifai.views import ListaPropiedadesPropifyView
from django.test import RequestFactory

def test_vista_sin_filtros():
    """Test: Vista sin filtros debe mostrar todas las propiedades."""
    print("=== Test 1: Vista sin filtros ===")
    
    # Crear request sin parámetros
    factory = RequestFactory()
    request = factory.get('/propifai/propiedades/')
    
    # Crear vista
    view = ListaPropiedadesPropifyView()
    view.request = request
    
    # Obtener queryset
    queryset = view.get_queryset()
    
    # Contar propiedades totales
    total_propiedades = PropifaiProperty.objects.count()
    propiedades_filtradas = queryset.count()
    
    print(f"Total propiedades en BD: {total_propiedades}")
    print(f"Propiedades en queryset (sin filtros): {propiedades_filtradas}")
    
    # Deberían ser iguales
    assert propiedades_filtradas == total_propiedades, \
        f"Error: Sin filtros debería mostrar todas las propiedades. Esperado: {total_propiedades}, Obtenido: {propiedades_filtradas}"
    
    print("OK Test 1 pasado: Sin filtros muestra todas las propiedades\n")

def test_vista_con_filtro_tipo():
    """Test: Vista con filtro de tipo."""
    print("=== Test 2: Vista con filtro de tipo ===")
    
    # Obtener un tipo de propiedad existente
    tipos = PropifaiProperty.objects.values_list('tipo_propiedad', flat=True).distinct()
    if tipos:
        tipo_ejemplo = tipos[0]
        
        # Crear request con parámetro
        factory = RequestFactory()
        request = factory.get(f'/propifai/propiedades/?tipo_propiedad={tipo_ejemplo}')
        
        # Crear vista
        view = ListaPropiedadesPropifyView()
        view.request = request
        
        # Obtener queryset
        queryset = view.get_queryset()
        
        # Verificar que todas las propiedades en el queryset tienen el tipo correcto
        for propiedad in queryset:
            assert tipo_ejemplo.lower() in propiedad.tipo_propiedad.lower(), \
                f"Error: Propiedad {propiedad.id} no tiene el tipo filtrado"
        
        print(f"Filtro aplicado: tipo_propiedad={tipo_ejemplo}")
        print(f"Propiedades filtradas: {queryset.count()}")
        print("OK Test 2 pasado: Filtro por tipo funciona correctamente\n")
    else:
        print("No hay tipos de propiedad en la BD para probar\n")

def test_vista_con_filtro_departamento():
    """Test: Vista con filtro de departamento."""
    print("=== Test 3: Vista con filtro de departamento ===")
    
    # Obtener un departamento existente
    departamentos = PropifaiProperty.objects.values_list('department', flat=True).distinct()
    departamentos = [d for d in departamentos if d]  # Filtrar valores no nulos
    
    if departamentos:
        depto_ejemplo = departamentos[0]
        
        # Crear request con parámetro
        factory = RequestFactory()
        request = factory.get(f'/propifai/propiedades/?departamento={depto_ejemplo}')
        
        # Crear vista
        view = ListaPropiedadesPropifyView()
        view.request = request
        
        # Obtener queryset
        queryset = view.get_queryset()
        
        # Verificar que todas las propiedades en el queryset tienen el departamento correcto
        for propiedad in queryset:
            assert depto_ejemplo.lower() in (propiedad.department or '').lower(), \
                f"Error: Propiedad {propiedad.id} no tiene el departamento filtrado"
        
        print(f"Filtro aplicado: departamento={depto_ejemplo}")
        print(f"Propiedades filtradas: {queryset.count()}")
        print("OK Test 3 pasado: Filtro por departamento funciona correctamente\n")
    else:
        print("No hay departamentos en la BD para probar\n")

def test_context_data():
    """Test: Context data incluye opciones de filtro."""
    print("=== Test 4: Context data ===")
    
    # Crear request
    factory = RequestFactory()
    request = factory.get('/propifai/propiedades/')
    
    # Crear vista
    view = ListaPropiedadesPropifyView()
    view.request = request
    view.object_list = view.get_queryset()
    
    # Obtener context data
    context = view.get_context_data()
    
    # Verificar que existen las claves necesarias
    claves_requeridas = [
        'total_propiedades',
        'propiedades_con_coordenadas',
        'titulo',
        'tipos_propiedad',
        'departamentos',
        'propiedades',
        'propiedades_compatibles',
        'parametros_filtro'
    ]
    
    for clave in claves_requeridas:
        assert clave in context, f"Error: Clave '{clave}' no encontrada en context"
        print(f"  OK Clave '{clave}' presente en context")
    
    print(f"  Total propiedades en context: {context['total_propiedades']}")
    print(f"  Tipos de propiedad disponibles: {len(context['tipos_propiedad'])}")
    print(f"  Departamentos disponibles: {len(context['departamentos'])}")
    print("OK Test 4 pasado: Context data completo\n")

def main():
    """Ejecutar todos los tests."""
    print("Iniciando pruebas de filtros Propify...\n")
    
    try:
        # Verificar que hay datos en la BD
        total = PropifaiProperty.objects.count()
        print(f"Propiedades Propify en base de datos: {total}\n")
        
        if total == 0:
            print("ADVERTENCIA: No hay propiedades en la BD. Algunos tests no se ejecutarán.")
            # Probar al menos la vista sin filtros
            test_vista_sin_filtros()
            test_context_data()
        else:
            test_vista_sin_filtros()
            test_vista_con_filtro_tipo()
            test_vista_con_filtro_departamento()
            test_context_data()
        
        print("=" * 50)
        print("¡Todas las pruebas completadas exitosamente!")
        print("La vista ahora muestra todas las propiedades cuando no hay filtros,")
        print("aplica filtros cuando se especifican, y se pueden limpiar con el botón 'Limpiar'.")
        
    except Exception as e:
        print(f"\n✗ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()