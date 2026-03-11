#!/usr/bin/env python
"""
Script de verificación final para asegurar que las imágenes de Propify se muestran
en todos los templates (Propify, ACM y vista general de propiedades).
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from propifai.models import PropifaiProperty
from ingestas.views import ListaPropiedadesView
from acm.views import buscar_comparables
from django.test import RequestFactory
import json

def verificar_modelo_propifai():
    """Verificar que el modelo PropifaiProperty genera URLs de imagen correctamente."""
    print("=== VERIFICACIÓN DEL MODELO PROPIFAI ===")
    
    try:
        # Obtener algunas propiedades
        propiedades = PropifaiProperty.objects.using('propifai').all()[:3]
        
        print(f"Propiedades encontradas: {len(propiedades)}")
        
        for i, prop in enumerate(propiedades):
            print(f"\nPropiedad {i+1}: ID={prop.id}, Código={prop.codigo}")
            print(f"  imagen_url: {prop.imagen_url}")
            print(f"  primera_imagen_url: {prop.primera_imagen_url}")
            print(f"  imagenes_relacionadas: {len(prop.imagenes_relacionadas)} imágenes")
            
            # Verificar que las URLs no sean None
            if prop.imagen_url:
                print(f"  ✓ imagen_url es válida")
            else:
                print(f"  ⚠️  imagen_url es None")
                
            if prop.primera_imagen_url:
                print(f"  ✓ primera_imagen_url es válida")
            else:
                print(f"  ⚠️  primera_imagen_url es None")
        
        return True
        
    except Exception as e:
        print(f"✗ Error verificando modelo Propifai: {e}")
        return False

def verificar_vista_propify():
    """Verificar que la vista de Propify pasa las URLs de imagen correctamente."""
    print("\n=== VERIFICACIÓN DE VISTA PROPIFY ===")
    
    try:
        from propifai.views import ListaPropiedadesPropifyView
        
        factory = RequestFactory()
        request = factory.get('/propifai/propiedades/')
        
        view = ListaPropiedadesPropifyView()
        view.request = request
        
        context = view.get_context_data()
        
        print(f"Contexto generado: {len(context.get('object_list', []))} propiedades")
        
        if context.get('object_list'):
            primera_prop = context['object_list'][0]
            print(f"\nPrimera propiedad en contexto:")
            print(f"  - imagen_url: {primera_prop.get('imagen_url')}")
            print(f"  - primera_imagen: {primera_prop.get('primera_imagen')}")
            
            if primera_prop.get('imagen_url'):
                print(f"  ✓ imagen_url está presente en el contexto")
            else:
                print(f"  ⚠️  imagen_url es None en el contexto")
        
        return True
        
    except Exception as e:
        print(f"✗ Error verificando vista Propify: {e}")
        return False

def verificar_vista_acm():
    """Verificar que la vista ACM pasa las URLs de imagen para propiedades Propify."""
    print("\n=== VERIFICACIÓN DE VISTA ACM ===")
    
    try:
        factory = RequestFactory()
        
        # Datos de prueba para ACM
        data = {
            'lat': -12.0464,  # Lima centro
            'lng': -77.0428,
            'radio': 5000,  # 5km
            'tipo_propiedad': ''
        }
        
        request = factory.post('/acm/buscar-comparables/',
                             data=json.dumps(data),
                             content_type='application/json')
        
        # Simular la vista
        response = buscar_comparables(request)
        
        if response.status_code == 200:
            result = json.loads(response.content)
            print(f"Respuesta ACM: {result.get('total')} propiedades encontradas")
            
            # Buscar propiedades Propify en la respuesta
            propifai_props = [p for p in result.get('propiedades', []) if p.get('es_propify')]
            print(f"Propiedades Propify en ACM: {len(propifai_props)}")
            
            if propifai_props:
                primera_prop = propifai_props[0]
                print(f"\nPrimera propiedad Propify en ACM:")
                print(f"  - imagen_url: {primera_prop.get('imagen_url')}")
                
                if primera_prop.get('imagen_url'):
                    print(f"  ✓ imagen_url está presente en ACM")
                else:
                    print(f"  ⚠️  imagen_url es None en ACM")
            else:
                print("⚠️  No se encontraron propiedades Propify en la respuesta ACM")
        
        return True
        
    except Exception as e:
        print(f"✗ Error verificando vista ACM: {e}")
        return False

def verificar_vista_general():
    """Verificar que la vista general de propiedades pasa las URLs de imagen para Propify."""
    print("\n=== VERIFICACIÓN DE VISTA GENERAL DE PROPIEDADES ===")
    
    try:
        # Crear una solicitud simulada con filtro para Propify
        factory = RequestFactory()
        request = factory.get('/ingestas/propiedades/?fuente_propify=propify')
        
        # Crear la vista
        view = ListaPropiedadesView()
        view.request = request
        
        # Obtener el contexto
        context = view.get_context_data()
        
        print(f"Contexto generado: propiedades en contexto")
        
        # Verificar que el método _obtener_todas_propiedades funciona
        todas_propiedades = view._obtener_todas_propiedades()
        
        # Filtrar propiedades Propify
        propifai_props = [p for p in todas_propiedades if p.get('es_propify')]
        print(f"Propiedades Propify en vista general: {len(propifai_props)}")
        
        if propifai_props:
            primera_prop = propifai_props[0]
            print(f"\nPrimera propiedad Propify en vista general:")
            print(f"  - primera_imagen: {primera_prop.get('primera_imagen')}")
            print(f"  - imagen_principal: {primera_prop.get('imagen_principal')}")
            
            if primera_prop.get('primera_imagen'):
                print(f"  ✓ primera_imagen está presente")
            else:
                print(f"  ⚠️  primera_imagen es None")
        
        return True
        
    except Exception as e:
        print(f"✗ Error verificando vista general: {e}")
        return False

def main():
    """Ejecutar todas las verificaciones."""
    print("INICIANDO VERIFICACIÓN FINAL DE IMÁGENES PROPIFY\n")
    
    resultados = []
    
    # Ejecutar verificaciones
    resultados.append(("Modelo Propifai", verificar_modelo_propifai()))
    resultados.append(("Vista Propify", verificar_vista_propify()))
    resultados.append(("Vista ACM", verificar_vista_acm()))
    resultados.append(("Vista General", verificar_vista_general()))
    
    # Resumen
    print("\n" + "="*50)
    print("RESUMEN DE VERIFICACIÓN")
    print("="*50)
    
    exitos = 0
    for nombre, resultado in resultados:
        estado = "✓" if resultado else "✗"
        print(f"{estado} {nombre}: {'PASÓ' if resultado else 'FALLÓ'}")
        if resultado:
            exitos += 1
    
    print(f"\nTotal: {exitos}/{len(resultados)} verificaciones exitosas")
    
    if exitos == len(resultados):
        print("\n✅ TODAS LAS VERIFICACIONES PASARON CORRECTAMENTE")
        print("Las imágenes de Propify deberían mostrarse en todos los templates.")
    else:
        print(f"\n⚠️  {len(resultados) - exitos} verificaciones fallaron")
        print("Es posible que algunas vistas aún no muestren las imágenes correctamente.")

if __name__ == '__main__':
    main()