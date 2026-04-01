#!/usr/bin/env python
"""
Script para verificar que las columnas del dashboard se muestren correctamente.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from propifai.models import PropifaiProperty
from propifai.views import dashboard_calidad_cartera
from django.test import RequestFactory

def test_columnas():
    """Probar que las columnas tengan datos correctos."""
    print("=== Verificación de columnas del dashboard ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/propifai/dashboard/calidad/')
    
    # Llamar a la vista
    response = dashboard_calidad_cartera(request)
    
    print(f"Status code: {response.status_code}")
    
    # Verificar contexto
    context = response.context_data
    if context:
        propiedades = context.get('propiedades', [])
        if propiedades:
            print(f"\nTotal propiedades en contexto: {len(propiedades)}")
            print("\nVerificación de las primeras 2 propiedades:")
            for i, prop in enumerate(propiedades[:2]):
                print(f"\nPropiedad {i+1}: {prop.code}")
                print(f"  - Título: {getattr(prop, 'title', 'N/A')}")
                print(f"  - Tipo de propiedad: {getattr(prop, 'property_type', 'N/A')}")
                print(f"  - Distrito: {getattr(prop, 'district_name', 'N/A')}")
                print(f"  - Precio: {getattr(prop, 'price', 'N/A')}")
                print(f"  - Días en publicación: {getattr(prop, 'dias_publicacion', 'N/A')}")
                print(f"  - Completitud score: {getattr(prop, 'completitud_score', 'N/A')}%")
                print(f"  - Fecha creación: {getattr(prop, 'created_at', 'N/A')}")
        
        # Verificar que todas las propiedades tengan dias_publicacion
        props_sin_dias = [p for p in propiedades if getattr(p, 'dias_publicacion', None) is None]
        print(f"\nPropiedades sin días en publicación: {len(props_sin_dias)}")
        
        # Verificar que todas tengan completitud_score
        props_sin_score = [p for p in propiedades if not hasattr(p, 'completitud_score')]
        print(f"Propiedades sin score de completitud: {len(props_sin_score)}")
        
        # Mostrar estadísticas de días
        dias_values = [getattr(p, 'dias_publicacion', 0) for p in propiedades if getattr(p, 'dias_publicacion', None) is not None]
        if dias_values:
            print(f"Días en publicación - Min: {min(dias_values)}, Max: {max(dias_values)}, Promedio: {sum(dias_values)/len(dias_values):.1f}")
    
    # También podemos verificar el HTML generado
    content = response.content.decode('utf-8')
    
    # Buscar algunas cadenas clave
    if "Días en publicación" in content:
        print("\n✅ Columna 'Días en publicación' encontrada en HTML")
    else:
        print("\n❌ Columna 'Días en publicación' NO encontrada en HTML")
        
    if "Completitud" in content:
        print("✅ Columna 'Completitud' encontrada en HTML")
    else:
        print("❌ Columna 'Completitud' NO encontrada en HTML")
        
    # Contar filas de la tabla
    import re
    row_matches = re.findall(r'<tr data-status="', content)
    print(f"Filas de propiedades en HTML: {len(row_matches)}")
    
    return response.status_code == 200

if __name__ == '__main__':
    try:
        success = test_columnas()
        if success:
            print("\n✅ Verificación de columnas completada.")
        else:
            print("\n❌ Hubo problemas con las columnas.")
    except Exception as e:
        print(f"\n❌ Error durante la verificación: {e}")
        import traceback
        traceback.print_exc()