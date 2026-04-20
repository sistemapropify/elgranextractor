#!/usr/bin/env python
"""
Script para probar consultas cruzadas entre bases de datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connection

def main():
    print("=== Probando consulta cruzada entre bases de datos ===")
    
    # Probar consulta usando nombre completo de tabla
    test_queries = [
        "SELECT COUNT(*) FROM [dbpropify].[dbo].[properties]",
        "SELECT TOP 1 id, title FROM [dbpropify].[dbo].[properties]",
        "SELECT TOP 1 id, title FROM properties",  # Sin nombre completo
    ]
    
    for i, query in enumerate(test_queries):
        print(f"\n--- Consulta {i+1}: {query[:50]}...")
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                print(f"   Resultado: {result}")
        except Exception as e:
            print(f"   ERROR: {e}")
    
    # También probar con conexión 'propifai'
    print("\n=== Probando con conexión 'propifai' ===")
    from django.db import connections
    conn = connections['propifai']
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM properties")
            result = cursor.fetchone()
            print(f"Conteo desde conexión 'propifai': {result[0]}")
    except Exception as e:
        print(f"ERROR con conexión 'propifai': {e}")

if __name__ == '__main__':
    main()