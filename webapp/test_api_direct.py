#!/usr/bin/env python
"""
Script para probar la API directamente y ver qué parámetros está recibiendo.
"""
import requests
import json

def test_api_with_params(schema='dbo', database='propifai', nocache=False):
    """Prueba la API con parámetros específicos."""
    url = 'http://127.0.0.1:8000/api/v1/intelligence/rag/tables/'
    params = {
        'schema': schema,
        'database': database,
    }
    if nocache:
        params['nocache'] = '1'
    
    print(f"\n=== Probando API con parámetros ===")
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Schema en respuesta: {data.get('schema')}")
            print(f"Database en respuesta: {data.get('database', 'NO INCLUIDO!')}")
            print(f"Count: {data.get('count')}")
            
            tables = data.get('tables', [])
            if tables:
                print(f"Primeras 10 tablas: {tables[:10]}")
                print(f"Total tablas: {len(tables)}")
                
                # Verificar si son tablas de propifai o default
                # Tablas típicas de propifai (vistas en el script anterior)
                propifai_tables = ['agency_config', 'canal_leads', 'properties', 'requirements', 'users']
                # Tablas típicas de default (vistas en la API)
                default_tables = ['auth_group', 'auth_group_permissions', 'auth_permission', 'auth_user', 'django_admin_log']
                
                propifai_count = sum(1 for table in tables if table in propifai_tables)
                default_count = sum(1 for table in tables if table in default_tables)
                
                print(f"Tablas de propifai encontradas: {propifai_count}/5")
                print(f"Tablas de default encontradas: {default_count}/5")
                
                if propifai_count > default_count:
                    print("CONCLUSIÓN: La API está devolviendo tablas de PROPIFAI")
                elif default_count > propifai_count:
                    print("CONCLUSIÓN: La API está devolviendo tablas de DEFAULT")
                else:
                    print("CONCLUSIÓN: No se puede determinar")
            else:
                print("No hay tablas en la respuesta")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Excepción: {e}")

def test_all_scenarios():
    """Prueba todos los escenarios posibles."""
    print("Iniciando pruebas de API...")
    
    # Escenario 1: database=propifai, sin cache
    test_api_with_params(database='propifai', nocache=True)
    
    # Escenario 2: database=propifai, con cache
    test_api_with_params(database='propifai', nocache=False)
    
    # Escenario 3: database=default, sin cache
    test_api_with_params(database='default', nocache=True)
    
    # Escenario 4: database=default, con cache
    test_api_with_params(database='default', nocache=False)
    
    # Escenario 5: Sin parámetro database (debería usar default)
    print("\n=== Probando API SIN parámetro database ===")
    url = 'http://127.0.0.1:8000/api/v1/intelligence/rag/tables/'
    response = requests.get(url, params={'schema': 'dbo'})
    if response.status_code == 200:
        data = response.json()
        print(f"Database en respuesta (sin especificar): {data.get('database', 'NO INCLUIDO')}")

if __name__ == '__main__':
    test_all_scenarios()