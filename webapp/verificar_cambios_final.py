#!/usr/bin/env python
"""
Script para verificar que los cambios finales están funcionando.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

def verificar_cambios():
    print("VERIFICACIÓN FINAL DE CAMBIOS")
    print("=" * 70)
    
    # Obtener algunas propiedades de ejemplo
    propiedades = PropifaiProperty.objects.all()[:5]
    
    print(f"\nTotal de propiedades en la base de datos: {PropifaiProperty.objects.count()}")
    print(f"Mostrando las primeras {len(propiedades)} propiedades:\n")
    
    for i, prop in enumerate(propiedades):
        print(f"--- PROPIEDAD {i+1} (ID: {prop.id}) ---")
        print(f"Título: {prop.title}")
        print(f"Código: {prop.code}")
        
        # Campos originales (índices)
        print(f"\nCAMPOS ORIGINALES (índices):")
        print(f"  department: '{prop.department}' (tipo: {type(prop.department).__name__})")
        print(f"  province: '{prop.province}' (tipo: {type(prop.province).__name__})")
        print(f"  district: '{prop.district}' (tipo: {type(prop.district).__name__})")
        
        # Campos mapeados (nombres)
        print(f"\nCAMPOS MAPEADOS (nombres):")
        print(f"  departamento_nombre: '{prop.departamento_nombre}'")
        print(f"  provincia_nombre: '{prop.provincia_nombre}'")
        print(f"  distrito_nombre: '{prop.distrito_nombre}'")
        
        # Ubicación formateada
        print(f"\nUBICACIÓN FORMATEADA:")
        print(f"  ubicacion_completa: '{prop.ubicacion_completa}'")
        print(f"  ubicacion_para_tarjeta: '{prop.ubicacion_para_tarjeta}'")
        
        # Verificar conversión
        depto_original = str(prop.department or '')
        depto_nombre = str(prop.departamento_nombre or '')
        
        if depto_original and depto_nombre and depto_original != depto_nombre:
            print(f"\n✓ CONVERSIÓN EXITOSA: '{depto_original}' -> '{depto_nombre}'")
        elif depto_original == depto_nombre:
            print(f"\n⚠ ADVERTENCIA: No hay conversión (mismo valor)")
        else:
            print(f"\n✗ ERROR: No se pudo obtener nombre mapeado")
        
        print("-" * 50)
    
    # Verificar mapeo de valores comunes
    print("\n" + "=" * 70)
    print("VERIFICACIÓN DE MAPEO DE VALORES COMUNES:")
    print("=" * 70)
    
    test_values = [
        ("4", "1", "1"),   # Arequipa, Arequipa, Arequipa
        ("4", "1", "4"),   # Arequipa, Arequipa, Cerro Colorado
        ("4", "1", "23"),  # Arequipa, Arequipa, Socabaya
    ]
    
    from propifai.mapeo_ubicaciones import (
        obtener_nombre_departamento,
        obtener_nombre_provincia,
        obtener_nombre_distrito
    )
    
    for dept_id, prov_id, dist_id in test_values:
        dept_nombre = obtener_nombre_departamento(dept_id)
        prov_nombre = obtener_nombre_provincia(prov_id)
        dist_nombre = obtener_nombre_distrito(dist_id)
        
        print(f"\nMapeo ID {dept_id}/{prov_id}/{dist_id}:")
        print(f"  Departamento: {dept_nombre}")
        print(f"  Provincia: {prov_nombre}")
        print(f"  Distrito: {dist_nombre}")
        
        if dept_nombre != dept_id:
            print(f"  ✓ Departamento convertido correctamente")
        if prov_nombre != prov_id:
            print(f"  ✓ Provincia convertida correctamente")
        if dist_nombre != dist_id:
            print(f"  ✓ Distrito convertido correctamente")
    
    print("\n" + "=" * 70)
    print("INSTRUCCIONES PARA VERIFICAR EN EL NAVEGADOR:")
    print("=" * 70)
    print("1. Visita http://localhost:8000/propifai/propiedades/")
    print("2. Las tarjetas deberían mostrar nombres como 'Arequipa, Arequipa, Arequipa'")
    print("3. Visita http://localhost:8000/ingestas/propiedades/")
    print("4. Activa el filtro 'Propify' para ver propiedades de Propifai")
    print("5. Las tarjetas deberían mostrar nombres en lugar de números")
    print("=" * 70)

if __name__ == '__main__':
    verificar_cambios()