#!/usr/bin/env python
"""
Script para probar la funcionalidad web del módulo de eventos usando requests.
"""
import sys
import requests
import time

def test_dashboard():
    """Prueba la vista principal del dashboard de eventos."""
    base_url = "http://localhost:8000"
    
    print("=== Prueba del dashboard de eventos (via HTTP) ===")
    
    # Prueba 1: Página principal sin filtros
    try:
        response = requests.get(f"{base_url}/eventos/", timeout=10)
        print(f"GET /eventos/ - Status: {response.status_code}")
        if response.status_code == 200:
            print("OK: Página cargada correctamente")
            # Verificar elementos clave
            if 'Eventos' in response.text:
                print("OK: Título 'Eventos' encontrado")
            if 'table' in response.text:
                print("OK: Tabla de eventos presente")
            if 'Filtrar' in response.text:
                print("OK: Formulario de filtros presente")
            # Contar eventos mostrados
            if 'eventos encontrados' in response.text.lower():
                print("OK: Contador de eventos presente")
            return True
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Contenido: {response.text[:500]}")
            return False
    except requests.exceptions.ConnectionError:
        print("ERROR: No se puede conectar al servidor. ¿Está ejecutándose?")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_filters():
    """Prueba los filtros del dashboard."""
    base_url = "http://localhost:8000"
    
    print("\n=== Prueba de filtros ===")
    
    filters = [
        ("dia", "2024-01-01"),
        ("propiedad", "123"),
        ("tipo", "1"),
        ("agente", "1"),
    ]
    
    for param, value in filters:
        try:
            response = requests.get(f"{base_url}/eventos/?{param}={value}", timeout=10)
            print(f"GET /eventos/?{param}={value} - Status: {response.status_code}")
            if response.status_code == 200:
                print(f"OK: Filtro por {param} funciona")
            else:
                print(f"ERROR: {response.status_code}")
        except Exception as e:
            print(f"ERROR en filtro {param}: {e}")

def test_pagination():
    """Prueba la paginación."""
    base_url = "http://localhost:8000"
    
    print("\n=== Prueba de paginación ===")
    
    try:
        response = requests.get(f"{base_url}/eventos/?page=2", timeout=10)
        print(f"GET /eventos/?page=2 - Status: {response.status_code}")
        if response.status_code == 200:
            print("OK: Paginación funciona")
        else:
            print(f"ERROR: {response.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == '__main__':
    print("Asegúrate de que el servidor Django esté ejecutándose en http://localhost:8000")
    print("Esperando 2 segundos para que el servidor esté listo...")
    time.sleep(2)
    
    success = test_dashboard()
    if success:
        test_filters()
        test_pagination()
        print("\n=== Todas las pruebas completadas ===")
    else:
        print("\n=== Pruebas fallidas ===")
        sys.exit(1)