#!/usr/bin/env python
"""
Script simple para probar ISJSON
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

def test_isjson():
    """Probar ISJSON con diferentes JSON"""
    
    try:
        # Obtener conexión a la base de datos propifai
        conn = connections['propifai']
        
        with conn.cursor() as cursor:
            # Probar diferentes casos
            test_cases = [
                ('{}', 'JSON vacío'),
                ('{"test": "value"}', 'JSON simple'),
                ('{"test": 123}', 'JSON con número entero'),
                ('{"test": 123.45}', 'JSON con decimal'),
                ('{"test": null}', 'JSON con null'),
                ('{"test": true}', 'JSON con true'),
                ('{"test": false}', 'JSON con false'),
                ('{"id": 2, "titulo": "Casa", "precio": 299000.0}', 'JSON similar al nuestro'),
                ('{"id": 2, "titulo": "Casa", "precio": 299000.0, "fecha": "2026-01-08T02:30:52.372341"}', 'JSON con fecha ISO'),
            ]
            
            print("Probando ISJSON con diferentes JSON:")
            for json_str, desc in test_cases:
                try:
                    # Usar parámetros correctamente
                    cursor.execute("SELECT ISJSON(?)", (json_str,))
                    result = cursor.fetchone()[0]
                    print(f"  {desc}: ISJSON = {result}")
                    if result == 0:
                        print(f"    ❌ JSON inválido: {json_str[:50]}...")
                except Exception as e:
                    print(f"  {desc}: ERROR - {e}")
            
            # Probar con el JSON exacto que generamos
            print("\n=== Probando con JSON exacto del sistema ===")
            
            # Generar JSON similar al del sistema
            import json
            import decimal
            import datetime
            
            test_data = {
                'id': 2,
                'titulo': 'Casa En Campo Verde - Cerro Colorado',
                'descripcion': 'Casa en Campo Verde - Cerro Colorado',
                'direccion': 'Urb. Campo Verde - Cerro Colorado, Arequipa',
                'distrito': '4',
                'condicion': 'sold',
                'precio': 299000.0,  # Decimal convertido a float
                'moneda': 'PEN',
                'area_construida': None,
                'area_total': None,
                'habitaciones': 5,
                'banos': 4,
                'estacionamientos': 1,
                'fecha_creacion': '2026-01-08T02:30:52.372341',  # datetime convertido a string ISO
                'es_propify': 1
            }
            
            json_str = json.dumps(test_data, ensure_ascii=False)
            print(f"JSON generado: {json_str[:100]}...")
            
            cursor.execute("SELECT ISJSON(?)", (json_str,))
            result = cursor.fetchone()[0]
            print(f"ISJSON resultado: {result}")
            
            if result == 0:
                print("❌ JSON no válido para SQL Server")
                
                # Probar con ensure_ascii=True
                json_str_ascii = json.dumps(test_data, ensure_ascii=True)
                print(f"\nProbando con ensure_ascii=True: {json_str_ascii[:100]}...")
                cursor.execute("SELECT ISJSON(?)", (json_str_ascii,))
                result_ascii = cursor.fetchone()[0]
                print(f"ISJSON con ensure_ascii=True: {result_ascii}")
                
                # Probar eliminando la fecha (podría ser el problema)
                test_data_no_date = test_data.copy()
                del test_data_no_date['fecha_creacion']
                json_str_no_date = json.dumps(test_data_no_date, ensure_ascii=False)
                print(f"\nProbando sin fecha: {json_str_no_date[:100]}...")
                cursor.execute("SELECT ISJSON(?)", (json_str_no_date,))
                result_no_date = cursor.fetchone()[0]
                print(f"ISJSON sin fecha: {result_no_date}")
                
                # Probar con formato de fecha diferente
                test_data_simple_date = test_data.copy()
                test_data_simple_date['fecha_creacion'] = '2026-01-08'
                json_str_simple_date = json.dumps(test_data_simple_date, ensure_ascii=False)
                print(f"\nProbando con fecha simple: {json_str_simple_date[:100]}...")
                cursor.execute("SELECT ISJSON(?)", (json_str_simple_date,))
                result_simple_date = cursor.fetchone()[0]
                print(f"ISJSON con fecha simple: {result_simple_date}")
                
    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=== Prueba simple ISJSON ===")
    test_isjson()