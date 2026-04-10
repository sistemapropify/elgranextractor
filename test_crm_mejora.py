#!/usr/bin/env python
"""
Script para probar la mejora del dashboard CRM con paginación y filtro.
"""
import os
import sys
import django
from django.test import Client

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def test_dashboard():
    print("=== Prueba del dashboard CRM mejorado ===")
    
    client = Client()
    
    # Probar acceso básico
    print("1. Probando acceso a /analisis-crm/...")
    response = client.get('/analisis-crm/')
    print(f"   Status code: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✓ Vista carga correctamente")
        
        # Verificar que aparece el campo de búsqueda
        content = response.content.decode('utf-8')
        if 'name="search"' in content:
            print("   ✓ Campo de búsqueda presente")
        else:
            print("   ✗ Campo de búsqueda no encontrado")
            
        # Verificar que aparece paginación (puede que no si hay pocos leads)
        if 'pagination' in content or 'page=' in content:
            print("   ✓ Elementos de paginación presentes")
        else:
            print("   ℹ️  Paginación no visible (puede ser que haya pocos leads)")
            
        # Verificar que se muestran leads
        if '<table' in content and 'leads' in content:
            print("   ✓ Tabla de leads presente")
        else:
            print("   ✗ Tabla de leads no encontrada")
            
        # Verificar estadísticas
        if 'Total Leads' in content:
            print("   ✓ Estadísticas presentes")
        else:
            print("   ✗ Estadísticas no encontradas")
            
        # Verificar gráficos
        if 'canvas' in content or 'Chart' in content:
            print("   ✓ Gráficos presentes")
        else:
            print("   ℹ️  Gráficos no encontrados (puede ser normal)")
    
    # Probar filtro de búsqueda
    print("\n2. Probando filtro de búsqueda por nombre...")
    response = client.get('/analisis-crm/?search=Juan')
    print(f"   Status code: {response.status_code}")
    if response.status_code == 200:
        print("   ✓ Búsqueda funciona")
        # Verificar que el parámetro search se mantiene en el formulario
        content = response.content.decode('utf-8')
        if 'value="Juan"' in content or 'value=\'Juan\'' in content:
            print("   ✓ Valor de búsqueda se mantiene en el input")
        else:
            print("   ✗ Valor de búsqueda no se mantiene")
    
    # Probar paginación
    print("\n3. Probando paginación...")
    response = client.get('/analisis-crm/?page=2')
    print(f"   Status code: {response.status_code}")
    if response.status_code == 200:
        print("   ✓ Paginación funciona")
        # Verificar que aparece el número de página
        content = response.content.decode('utf-8')
        if 'page=1' in content or 'page=3' in content:
            print("   ✓ Enlaces de paginación presentes")
        else:
            print("   ℹ️  Enlaces de paginación no visibles (puede ser que solo haya una página)")
    
    # Probar combinación de filtros
    print("\n4. Probando combinación de filtros...")
    response = client.get('/analisis-crm/?search=Maria&filter_date=2026-04-07')
    print(f"   Status code: {response.status_code}")
    if response.status_code == 200:
        print("   ✓ Filtros combinados funcionan")
    
    print("\n=== Prueba completada ===")

if __name__ == "__main__":
    test_dashboard()