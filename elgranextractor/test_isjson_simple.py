#!/usr/bin/env python
"""
Test simple de ISJSON sin caracteres Unicode
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

def test_isjson():
    """Test ISJSON directamente"""
    
    print("DEBUG: Probando ISJSON con diferentes variantes")
    
    # JSON que estamos generando (copiado del output anterior)
    our_json = '{"id": 2, "titulo": "Casa En Campo Verde - Cerro Colorado", "descripcion": "Casa en Campo Verde - Cerro Colorado", "direccion": "Urb. Campo Verde - Cerro Colorado, Arequipa", "distrito": "4", "condicion": "sold", "precio": 299000.0, "moneda": "PEN", "area_construida": null, "area_total": null, "habitaciones": 5, "banos": 4, "estacionamientos": 1, "fecha_creacion": "2026-01-08 02:30:52", "es_propify": 1}'
    
    print(f"Nuestro JSON: {our_json[:100]}...")
    print(f"Longitud: {len(our_json)}")
    
    try:
        # Probar parseo en Python
        parsed = json.loads(our_json)
        print("OK - JSON valido en Python")
        
        # Conectar a base de datos
        conn = connections['default']
        
        with conn.cursor() as cursor:
            # Probar ISJSON directamente con string literal
            print("\nProbando ISJSON con string literal...")
            
            # Probar diferentes variantes
            test_cases = [
                ("SELECT ISJSON('{}')", "JSON vacio"),
                ("SELECT ISJSON('{\"test\": 1}')", "JSON simple"),
                ("SELECT ISJSON('{\"test\": 1.5}')", "JSON con decimal"),
                ("SELECT ISJSON('{\"test\": null}')", "JSON con null"),
                ("SELECT ISJSON('{\"test\": \"hello\"}')", "JSON con string"),
                # Nuestro JSON como string literal (escapado)
                ("SELECT ISJSON('{\"id\": 2, \"test\": \"value\"}')", "JSON simple similar"),
            ]
            
            for sql, desc in test_cases:
                try:
                    cursor.execute(sql)
                    result = cursor.fetchone()[0]
                    print(f"  {desc}: {result}")
                except Exception as e:
                    print(f"  {desc}: ERROR - {e}")
            
            # Ahora probar con parámetro
            print("\nProbando con parametro...")
            
            # Primero probar con JSON simple
            simple_json = '{"test": 1}'
            try:
                # Usar execute con parámetros
                cursor.execute("SELECT ISJSON(%s)", (simple_json,))
                result = cursor.fetchone()[0]
                print(f"  JSON simple con parametro: {result}")
            except Exception as e:
                print(f"  ERROR con parametro: {e}")
            
            # Probar nuestro JSON
            try:
                cursor.execute("SELECT ISJSON(%s)", (our_json,))
                result = cursor.fetchone()[0]
                print(f"  Nuestro JSON con parametro: {result}")
            except Exception as e:
                print(f"  ERROR con nuestro JSON: {e}")
            
            # Probar insertar directamente en la tabla
            print("\nProbando insercion directa en SQL...")
            
            # Crear una tabla temporal para prueba
            try:
                cursor.execute("""
                    CREATE TABLE #test_json (
                        id INT IDENTITY(1,1),
                        metadata_json NVARCHAR(MAX) CHECK (ISJSON(metadata_json)=1)
                    )
                """)
                
                # Intentar insertar nuestro JSON
                try:
                    cursor.execute("INSERT INTO #test_json (metadata_json) VALUES (%s)", (our_json,))
                    print("  OK - Insercion exitosa en tabla temporal")
                except Exception as e:
                    print(f"  ERROR insertando: {e}")
                    
                    # Probar con JSON más simple
                    simple = '{"test": 1}'
                    try:
                        cursor.execute("INSERT INTO #test_json (metadata_json) VALUES (%s)", (simple,))
                        print("  OK - JSON simple insertado correctamente")
                    except Exception as e2:
                        print(f"  ERROR incluso con JSON simple: {e2}")
                
                # Limpiar tabla temporal
                cursor.execute("DROP TABLE #test_json")
                
            except Exception as e:
                print(f"  ERROR creando tabla temporal: {e}")
                
    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    test_isjson()