#!/usr/bin/env python
"""
Script para probar la vista ListaPropiedadesView con la segunda base de datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

def test_vista():
    """Probar la vista ListaPropiedadesView."""
    print("=== Probando ListaPropiedadesView con segunda base de datos ===")
    
    # Crear una solicitud simulada
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/', {
        'fuente_local': 'on',
        'fuente_externa': 'on',
        'fuente_propify': 'on'
    })
    
    # Crear la vista
    view = ListaPropiedadesView()
    view.request = request
    
    try:
        # Obtener el contexto
        context = view.get_context_data()
        
        print(f"✓ Vista ejecutada exitosamente")
        print(f"  Total propiedades: {context.get('total_propiedades', 0)}")
        print(f"  Conteo locales: {context.get('conteo_locales', 0)}")
        print(f"  Conteo externas: {context.get('conteo_externas', 0)}")
        print(f"  Conteo propify: {context.get('conteo_propify', 0)}")
        print(f"  Todas propiedades: {len(context.get('todas_propiedades', []))}")
        
        # Verificar que todas las propiedades sean diccionarios
        todas_propiedades = context.get('todas_propiedades', [])
        if todas_propiedades:
            for i, prop in enumerate(todas_propiedades[:3]):
                print(f"  Propiedad {i+1}: {type(prop).__name__} - ID: {prop.get('id', 'N/A')}")
        
        print("\n✓ Verificación de tipos de datos:")
        for prop in todas_propiedades[:5]:
            if not isinstance(prop, dict):
                print(f"  ERROR: Propiedad no es diccionario: {type(prop)}")
                return False
        
        print("  Todas las propiedades son diccionarios ✓")
        
        # Verificar que no haya errores de VariableDoesNotExist
        print("\n✓ Verificación de campos requeridos:")
        campos_requeridos = ['id', 'id_externo', 'es_externo', 'tipo_propiedad']
        for prop in todas_propiedades[:5]:
            for campo in campos_requeridos:
                if campo not in prop:
                    print(f"  ADVERTENCIA: Campo '{campo}' no encontrado en propiedad ID: {prop.get('id', 'N/A')}")
        
        print("\n=== Prueba completada exitosamente ===")
        return True
        
    except Exception as e:
        print(f"✗ Error al ejecutar la vista: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_vista()
    sys.exit(0 if success else 1)