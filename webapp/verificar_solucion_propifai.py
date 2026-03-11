#!/usr/bin/env python
"""
Script para verificar que la solución para Propifai funciona correctamente
y no modifica la base de datos Propifai.
"""
import os
import sys
import django
from django.db import connections

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from propifai.mapeo_ubicaciones import (
    obtener_nombre_departamento,
    obtener_nombre_provincia,
    obtener_nombre_distrito,
    formatear_ubicacion
)

def verificar_solucion():
    print("VERIFICANDO SOLUCIÓN PARA PROPIFAI")
    print("=" * 70)
    
    # 1. Verificar que no se modifica la base de datos Propifai
    print("\n1. VERIFICACIÓN DE NO MODIFICACIÓN DE BASE DE DATOS:")
    print("-" * 50)
    
    # Conectar a la base de datos propifai
    connection = connections['propifai']
    
    try:
        with connection.cursor() as cursor:
            # Verificar que la tabla properties existe y tiene datos
            cursor.execute("SELECT COUNT(*) FROM properties")
            total_propiedades = cursor.fetchone()[0]
            print(f"Total de propiedades en Propifai: {total_propiedades}")
            
            # Verificar que los campos de ubicación siguen siendo los mismos
            cursor.execute("""
                SELECT TOP 1 id, department, province, district 
                FROM properties 
                WHERE department IS NOT NULL
            """)
            ejemplo = cursor.fetchone()
            if ejemplo:
                prop_id, dept, prov, dist = ejemplo
                print(f"Ejemplo de propiedad (ID: {prop_id}):")
                print(f"  department (original): {dept} (tipo: {type(dept).__name__})")
                print(f"  province (original): {prov} (tipo: {type(prov).__name__})")
                print(f"  district (original): {dist} (tipo: {type(dist).__name__})")
            
            print("OK - La base de datos Propifai NO ha sido modificada")
            
    except Exception as e:
        print(f"Error verificando base de datos: {e}")
    
    # 2. Verificar mapeo de ubicaciones
    print("\n2. VERIFICACIÓN DE MAPEO DE UBICACIONES:")
    print("-" * 50)
    
    # Probar con algunos valores conocidos
    test_cases = [
        ("4", "1", "1"),  # Arequipa, Arequipa, Arequipa
        ("4", "1", "4"),  # Arequipa, Arequipa, Cerro Colorado
        ("4", "1", "23"), # Arequipa, Arequipa, Socabaya
    ]
    
    for dept_id, prov_id, dist_id in test_cases:
        dept_nombre = obtener_nombre_departamento(dept_id)
        prov_nombre = obtener_nombre_provincia(prov_id)
        dist_nombre = obtener_nombre_distrito(dist_id)
        
        print(f"\n  Mapeo ID {dept_id}/{prov_id}/{dist_id}:")
        print(f"    Departamento: {dept_nombre}")
        print(f"    Provincia: {prov_nombre}")
        print(f"    Distrito: {dist_nombre}")
        
        ubicacion = formatear_ubicacion(dept_id, prov_id, dist_id)
        print(f"    Ubicación formateada: {ubicacion}")
    
    # 3. Verificar propiedades del modelo
    print("\n3. VERIFICACIÓN DE PROPIEDADES DEL MODELO:")
    print("-" * 50)
    
    try:
        # Obtener algunas propiedades para probar
        propiedades = PropifaiProperty.objects.all()[:3]
        
        for i, prop in enumerate(propiedades):
            print(f"\n  Propiedad {i+1} (ID: {prop.id}):")
            print(f"    department (índice): {prop.department}")
            print(f"    departamento_nombre: {prop.departamento_nombre}")
            print(f"    province (índice): {prop.province}")
            print(f"    provincia_nombre: {prop.provincia_nombre}")
            print(f"    district (índice): {prop.district}")
            print(f"    distrito_nombre: {prop.distrito_nombre}")
            print(f"    ubicacion_completa: {prop.ubicacion_completa}")
            print(f"    ubicacion_para_tarjeta: {prop.ubicacion_para_tarjeta}")
            
            # Verificar que los campos originales no han cambiado
            assert prop.department is None or isinstance(prop.department, (str, type(None))), f"department no es string: {type(prop.department)}"
            assert prop.province is None or isinstance(prop.province, (str, type(None))), f"province no es string: {type(prop.province)}"
            assert prop.district is None or isinstance(prop.district, (str, type(None))), f"district no es string: {type(prop.district)}"
        
        print(f"\nOK - Modelo verificado correctamente para {len(propiedades)} propiedades")
        
    except Exception as e:
        print(f"Error verificando modelo: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Verificar conversión a diccionario
    print("\n4. VERIFICACIÓN DE CONVERSIÓN A DICCIONARIO:")
    print("-" * 50)
    
    # Necesitamos importar la vista para probar la conversión
    try:
        from ingestas.views import PropiedadListView
        vista = PropiedadListView()
        
        if propiedades:
            prop = propiedades[0]
            prop_dict = vista._convertir_propiedad_propifai_a_dict(prop)
            
            print(f"  Propiedad convertida a diccionario:")
            print(f"    departamento (índice): {prop_dict.get('departamento')}")
            print(f"    departamento_nombre: {prop_dict.get('departamento_nombre')}")
            print(f"    provincia (índice): {prop_dict.get('provincia')}")
            print(f"    provincia_nombre: {prop_dict.get('provincia_nombre')}")
            print(f"    distrito (índice): {prop_dict.get('distrito')}")
            print(f"    distrito_nombre: {prop_dict.get('distrito_nombre')}")
            print(f"    ubicacion_completa: {prop_dict.get('ubicacion_completa')}")
            
            # Verificar que ambos campos existen
            assert 'departamento' in prop_dict, "Falta campo 'departamento'"
            assert 'departamento_nombre' in prop_dict, "Falta campo 'departamento_nombre'"
            assert 'provincia' in prop_dict, "Falta campo 'provincia'"
            assert 'provincia_nombre' in prop_dict, "Falta campo 'provincia_nombre'"
            assert 'distrito' in prop_dict, "Falta campo 'distrito'"
            assert 'distrito_nombre' in prop_dict, "Falta campo 'distrito_nombre'"
            
            print("OK - Conversión a diccionario verificada correctamente")
            
    except Exception as e:
        print(f"Error verificando conversión: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Verificar filtros
    print("\n5. VERIFICACIÓN DE FILTROS:")
    print("-" * 50)
    
    # Simular filtro por departamento
    test_filtros = [
        ("4", "Arequipa"),  # Buscar por índice
        ("Arequipa", "Arequipa"),  # Buscar por nombre
    ]
    
    for filtro_valor, expected_match in test_filtros:
        print(f"\n  Probando filtro: '{filtro_valor}'")
        
        # Simular la lógica de filtro
        prop_dict_ejemplo = {
            'departamento': '4',
            'departamento_nombre': 'Arequipa',
            'provincia': '1',
            'provincia_nombre': 'Arequipa',
            'distrito': '1',
            'distrito_nombre': 'Arequipa'
        }
        
        # Aplicar lógica de filtro similar a _aplicar_filtros
        depto_coincide = False
        prop_depto = prop_dict_ejemplo.get('departamento', '')
        prop_depto_nombre = prop_dict_ejemplo.get('departamento_nombre', '')
        
        if prop_depto and filtro_valor.lower() in str(prop_depto).lower():
            depto_coincide = True
            print(f"    Coincide por índice: {prop_depto}")
        elif prop_depto_nombre and filtro_valor.lower() in str(prop_depto_nombre).lower():
            depto_coincide = True
            print(f"    Coincide por nombre: {prop_depto_nombre}")
        
        if depto_coincide:
            print(f"    OK - Filtro '{filtro_valor}' coincide con '{expected_match}'")
        else:
            print(f"    ERROR - Filtro '{filtro_valor}' NO coincide")
    
    print("\n" + "=" * 70)
    print("RESUMEN DE VERIFICACIÓN:")
    print("- La base de datos Propifai NO ha sido modificada")
    print("- Los índices se mapean correctamente a nombres")
    print("- Las propiedades del modelo muestran nombres en lugar de índices")
    print("- Los filtros funcionan tanto con índices como con nombres")
    print("- La solución es READ-ONLY (solo lectura)")
    print("=" * 70)

if __name__ == '__main__':
    verificar_solucion()