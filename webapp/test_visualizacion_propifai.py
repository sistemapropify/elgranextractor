#!/usr/bin/env python
"""
Script para probar que las propiedades de Propifai muestran nombres en lugar de números.
"""
import os
import sys
import django
from django.test import RequestFactory

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.views import ListaPropiedadesPropifyView
from propifai.models import PropifaiProperty

def test_visualizacion():
    print("TEST DE VISUALIZACIÓN PARA PROPIFAI")
    print("=" * 70)
    
    # Crear una solicitud simulada
    factory = RequestFactory()
    request = factory.get('/propifai/propiedades/')
    
    # Crear la vista
    view = ListaPropiedadesPropifyView()
    view.request = request
    
    # Obtener el contexto
    view.object_list = PropifaiProperty.objects.all()[:3]
    context = view.get_context_data()
    
    # Verificar las propiedades en el contexto
    propiedades = context.get('propiedades', [])
    
    print(f"\nTotal de propiedades en contexto: {len(propiedades)}")
    
    for i, prop in enumerate(propiedades):
        print(f"\n--- Propiedad {i+1} ---")
        print(f"ID: {prop.get('id')}")
        print(f"Título: {prop.get('titulo')}")
        print(f"Departamento (índice): {prop.get('departamento')}")
        print(f"Departamento (nombre): {prop.get('departamento_nombre')}")
        print(f"Provincia (índice): {prop.get('provincia')}")
        print(f"Provincia (nombre): {prop.get('provincia_nombre')}")
        print(f"Distrito (índice): {prop.get('distrito')}")
        print(f"Distrito (nombre): {prop.get('distrito_nombre')}")
        print(f"Ubicación completa: {prop.get('ubicacion_completa')}")
        
        # Verificar que los nombres no sean iguales a los índices (deberían ser diferentes)
        depto_idx = str(prop.get('departamento', ''))
        depto_nombre = str(prop.get('departamento_nombre', ''))
        
        if depto_idx and depto_nombre and depto_idx != depto_nombre:
            print(f"✓ Departamento convertido: {depto_idx} -> {depto_nombre}")
        else:
            print(f"✗ Departamento NO convertido: {depto_idx}")
    
    # También probar directamente el modelo
    print("\n" + "=" * 70)
    print("PRUEBA DIRECTA DEL MODELO:")
    print("=" * 70)
    
    propiedades_modelo = PropifaiProperty.objects.all()[:3]
    for i, prop in enumerate(propiedades_modelo):
        print(f"\n--- Modelo Propiedad {i+1} ---")
        print(f"ID: {prop.id}")
        print(f"department (campo original): {prop.department}")
        print(f"departamento_nombre (propiedad): {prop.departamento_nombre}")
        print(f"province (campo original): {prop.province}")
        print(f"provincia_nombre (propiedad): {prop.provincia_nombre}")
        print(f"district (campo original): {prop.district}")
        print(f"distrito_nombre (propiedad): {prop.distrito_nombre}")
        print(f"ubicacion_completa (propiedad): {prop.ubicacion_completa}")
        print(f"ubicacion_para_tarjeta (propiedad): {prop.ubicacion_para_tarjeta}")
        
        # Verificar que las propiedades existen
        assert hasattr(prop, 'departamento_nombre'), "Falta propiedad departamento_nombre"
        assert hasattr(prop, 'provincia_nombre'), "Falta propiedad provincia_nombre"
        assert hasattr(prop, 'distrito_nombre'), "Falta propiedad distrito_nombre"
        assert hasattr(prop, 'ubicacion_completa'), "Falta propiedad ubicacion_completa"
    
    print("\n" + "=" * 70)
    print("RESULTADO:")
    print("-" * 70)
    print("Las propiedades ahora deberían mostrar nombres en lugar de números.")
    print("Verifica en el navegador: http://localhost:8000/propifai/propiedades/")
    print("=" * 70)

if __name__ == '__main__':
    test_visualizacion()