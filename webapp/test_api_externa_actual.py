#!/usr/bin/env python
"""
Script para probar la API externa de propiedades.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.services_api import obtener_propiedades_externas

def main():
    print("=== Probando API Externa de Propiedades ===")
    print("Obteniendo propiedades externas...")
    
    propiedades = obtener_propiedades_externas()
    
    if propiedades:
        print(f"✓ Se obtuvieron {len(propiedades)} propiedades externas")
        for i, prop in enumerate(propiedades[:3]):  # Mostrar primeras 3
            print(f"\nPropiedad {i+1}:")
            print(f"  ID Externo: {prop.get('id_externo')}")
            print(f"  Tipo: {prop.get('tipo_propiedad')}")
            print(f"  Descripción: {prop.get('descripcion')[:50]}...")
            print(f"  Precio USD: {prop.get('precio_usd')}")
            print(f"  Departamento: {prop.get('departamento')}")
            print(f"  Es externo: {prop.get('es_externo')}")
        if len(propiedades) > 3:
            print(f"\n... y {len(propiedades) - 3} propiedades más.")
    else:
        print("✗ No se obtuvieron propiedades externas (puede que la API no esté disponible o haya error)")
    
    print("\n=== Prueba completada ===")

if __name__ == '__main__':
    main()