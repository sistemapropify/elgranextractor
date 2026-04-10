#!/usr/bin/env python
"""
Script para probar el dashboard de eventos y verificar que se muestran nombres de agentes.
"""
import os
import sys
import django
from django.test import Client
from django.urls import reverse

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def test_dashboard():
    """Probar la vista dashboard usando Django test client."""
    print("=== Prueba del dashboard de eventos ===")
    
    client = Client()
    
    # Probar acceso a la vista principal
    url = reverse('eventos:dashboard_eventos')
    print(f"URL: {url}")
    
    response = client.get(url)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ Vista carga correctamente")
        
        # Verificar contenido
        content = response.content.decode('utf-8')
        
        # Verificar que aparecen nombres de agentes conocidos
        nombres_agentes = [
            "brayan Tong",
            "Veronica Alejandra Palacios Trigoso", 
            "Valery Gonzales Pastor"
        ]
        
        for nombre in nombres_agentes:
            if nombre in content:
                print(f"✓ Nombre de agente encontrado: {nombre}")
            else:
                print(f"✗ Nombre de agente no encontrado: {nombre}")
        
        # Verificar que no aparece "Agente #" para los IDs que tienen nombre
        if "Agente #7" in content:
            print("✗ Aún aparece 'Agente #7' (debería mostrar nombre)")
        else:
            print("✓ No aparece 'Agente #7' (bueno, se muestra nombre)")
            
        if "Agente #6" in content:
            print("✗ Aún aparece 'Agente #6' (debería mostrar nombre)")
        else:
            print("✓ No aparece 'Agente #6' (bueno, se muestra nombre)")
        
        # Verificar que la tabla se renderiza
        if "<table" in content and "eventos_con_propiedad" in content:
            print("✓ Tabla de eventos se renderiza correctamente")
        else:
            print("✗ Tabla de eventos no se encuentra en el HTML")
            
        # Verificar paginación
        if "pagination" in content or "Paginación" in content:
            print("✓ Paginación presente")
        else:
            print("✗ Paginación no encontrada")
            
        # Verificar filtros
        if "Filtrar" in content or "filtrosModal" in content:
            print("✓ Filtros presentes")
        else:
            print("✗ Filtros no encontrados")
            
        # Verificar propiedades y coordenadas
        if "title" in content and "coordinates" in content:
            print("✓ Información de propiedades presente")
        else:
            print("✗ Información de propiedades no encontrada")
            
        # Verificar mapa Leaflet
        if "leaflet" in content.lower() or "L.map" in content:
            print("✓ Mapa Leaflet integrado")
        else:
            print("✗ Mapa Leaflet no encontrado")
            
    else:
        print(f"✗ Error en la vista: {response.status_code}")
        print(f"Contenido: {response.content[:500]}")

if __name__ == "__main__":
    test_dashboard()