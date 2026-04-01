#!/usr/bin/env python
"""
Script para verificar que el dashboard final funciona correctamente.
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

def test_dashboard_view():
    """Probar la vista del dashboard."""
    print("=== Test Dashboard Calidad Cartera ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/propifai/dashboard/calidad/')
    
    # Llamar a la vista
    from propifai.views import dashboard_calidad_cartera
    response = dashboard_calidad_cartera(request)
    
    print(f"Status code: {response.status_code}")
    print(f"Template usado: {response.template_name}")
    
    # Verificar contexto
    context = response.context_data
    if context:
        print(f"\nContexto disponible:")
        print(f"- Total propiedades: {context.get('total_real')}")
        print(f"- Propiedades disponibles (no borradores): {context.get('props_disponibles')}")
        print(f"- Propiedades borradores: {context.get('props_borradores')}")
        print(f"- Completitud promedio: {context.get('completitud_promedio'):.1f}%")
        
        # Verificar algunas propiedades
        propiedades = context.get('propiedades', [])
        if propiedades:
            print(f"\nPrimeras 3 propiedades:")
            for i, prop in enumerate(propiedades[:3]):
                print(f"  {i+1}. Código: {prop.code}, Tipo: {getattr(prop, 'property_type', 'N/A')}, "
                      f"Distrito: {getattr(prop, 'district_name', 'N/A')}, "
                      f"Completitud: {getattr(prop, 'completitud_score', 0)}%")
        
        # Verificar stats_por_tipo
        stats_por_tipo = context.get('stats_por_tipo', [])
        if stats_por_tipo:
            print(f"\nEstadísticas por tipo:")
            for stat in stats_por_tipo:
                print(f"  - {stat['tipo']}: {stat['num_props']} propiedades")
    
    return response.status_code == 200

def test_property_types():
    """Verificar que los tipos de propiedad sean correctos."""
    print("\n=== Verificación de tipos de propiedad ===")
    
    # Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.all()[:10]
    
    print(f"Muestra de {propiedades.count()} propiedades:")
    for prop in propiedades:
        # Obtener property_type desde la vista (simulando la lógica)
        from django.db import connections
        conn = connections['propifai']
        property_type_map = {}
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM property_types")
            for row in cursor.fetchall():
                property_type_map[row[0]] = row[1]
        
        # Obtener property_type_id para esta propiedad
        prop_extras = {}
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, property_type_id, created_by_id FROM properties WHERE id = %s", [prop.id])
            row = cursor.fetchone()
            if row:
                prop_id, pt_id, cb_id = row
                prop_extras[prop_id] = {'property_type_id': pt_id, 'created_by_id': cb_id}
        
        tipo = '—'
        if prop.id in prop_extras:
            pt_id = prop_extras[prop.id]['property_type_id']
            if pt_id and pt_id in property_type_map:
                tipo = property_type_map[pt_id]
        
        print(f"  - {prop.code}: '{tipo}' (title: {prop.title[:30] if prop.title else 'N/A'})")

if __name__ == '__main__':
    try:
        success = test_dashboard_view()
        test_property_types()
        if success:
            print("\n✅ Dashboard funciona correctamente.")
        else:
            print("\n❌ Hubo problemas con el dashboard.")
    except Exception as e:
        print(f"\n❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()