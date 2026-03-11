#!/usr/bin/env python3
"""
Diagnóstico del problema con Propifai
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def diagnosticar_propifai():
    print("=== DIAGNOSTICO PROPIY ===")
    
    # 1. Verificar si se puede importar el modelo
    try:
        from propifai.models import PropifaiProperty
        print("OK - Modelo PropifaiProperty importado correctamente")
    except Exception as e:
        print(f"ERROR - No se puede importar PropifaiProperty: {e}")
        return
    
    # 2. Verificar conexión a la base de datos
    try:
        count = PropifaiProperty.objects.count()
        print(f"OK - Conexión a BD: {count} propiedades en total")
    except Exception as e:
        print(f"ERROR - No se puede conectar a la BD Propifai: {e}")
        return
    
    # 3. Verificar algunas propiedades
    try:
        propiedades = list(PropifaiProperty.objects.all()[:5])
        print(f"OK - Se obtuvieron {len(propiedades)} propiedades (primeras 5)")
        
        for i, prop in enumerate(propiedades):
            print(f"  Propiedad {i+1}: ID={prop.id}, code={prop.code}, lat={prop.latitude}, lng={prop.longitude}")
    except Exception as e:
        print(f"ERROR - No se pueden obtener propiedades: {e}")
    
    # 4. Verificar la conversión a diccionario
    from ingestas.views import ListaPropiedadesView
    view = ListaPropiedadesView()
    
    try:
        if propiedades:
            prop_dict = view._convertir_propiedad_propifai_a_dict(propiedades[0])
            print(f"\nOK - Conversión a diccionario exitosa")
            print(f"  es_propify: {prop_dict.get('es_propify', 'NO EXISTE')}")
            print(f"  es_externo: {prop_dict.get('es_externo', 'NO EXISTE')}")
            print(f"  lat/lng: {prop_dict.get('lat', 'N/A')}, {prop_dict.get('lng', 'N/A')}")
            print(f"  Todos los campos: {list(prop_dict.keys())}")
        else:
            print("\nADVERTENCIA - No hay propiedades para probar conversión")
    except Exception as e:
        print(f"ERROR - Falló la conversión a diccionario: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Verificar _obtener_todas_propiedades con filtro Propify
    print("\n=== PRUEBA DE _obtener_todas_propiedades CON FILTRO PROPIY ===")
    
    from django.test import RequestFactory
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})
    
    view2 = ListaPropiedadesView()
    view2.request = request
    
    try:
        todas = view2._obtener_todas_propiedades()
        print(f"Total propiedades obtenidas: {len(todas)}")
        
        # Contar por tipo
        propify_count = sum(1 for p in todas if isinstance(p, dict) and p.get('es_propify'))
        externo_count = sum(1 for p in todas if isinstance(p, dict) and p.get('es_externo') and not p.get('es_propify'))
        local_count = sum(1 for p in todas if isinstance(p, dict) and not p.get('es_externo'))
        
        print(f"  Propify: {propify_count}")
        print(f"  Externas: {externo_count}")
        print(f"  Locales: {local_count}")
        
        if propify_count == 0:
            print("\nPROBLEMA: _obtener_todas_propiedades no devuelve propiedades Propify")
            print("Posibles causas:")
            print("1. fuente_propify no es True (verificar _calcular_checkboxes)")
            print("2. propiedades_propifai_dict está vacío")
            print("3. Error en la intercalación")
        else:
            print("\nOK - _obtener_todas_propiedades devuelve propiedades Propify")
            
    except Exception as e:
        print(f"ERROR - Falló _obtener_todas_propiedades: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnosticar_propifai()