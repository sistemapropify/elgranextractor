#!/usr/bin/env python
"""
Script para probar ISJSON con datos reales
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from django.db import connections

def test_isjson():
    """Probar ISJSON con datos reales"""
    
    try:
        # Obtener conexión a la base de datos propifai
        conn = connections['propifai']
        
        with conn.cursor() as cursor:
            # Ejecutar consulta de la colección
            cursor.execute("""
                SELECT TOP 5
                    p.id,
                    p.title as titulo,
                    p.description as descripcion,
                    p.real_address as direccion,
                    p.district as distrito,
                    p.condition as condicion,
                    p.price as precio,
                    p.area as area,
                    p.created_at as fecha_creacion
                FROM properties p
                WHERE p.price IS NOT NULL
            """)
            
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            
            print(f"Obtenidos {len(rows)} registros de prueba")
            
            for i, row in enumerate(rows):
                row_dict = dict(zip(columns, row))
                print(f"\n--- Registro {i+1} ---")
                
                # Mostrar tipos de datos
                for key, value in row_dict.items():
                    if value is not None:
                        print(f"  {key}: {type(value).__name__}")
                
                # Serializar
                serialized = RAGService._serialize_row_dict(row_dict)
                json_str = json.dumps(serialized, ensure_ascii=False)
                
                # Probar ISJSON
                print(f"  Probando ISJSON...")
                try:
                    cursor.execute("SELECT ISJSON(?)", [json_str])
                    is_json_result = cursor.fetchone()[0]
                    print(f"  ISJSON devuelve: {is_json_result}")
                    
                    if is_json_result == 0:
                        print(f"  ERROR: JSON no válido para SQL Server")
                        print(f"  JSON (primeros 200 chars): {json_str[:200]}")
                        
                        # Probar con JSON simple
                        cursor.execute("SELECT ISJSON('{}')")
                        print(f"  ISJSON('{{}}'): {cursor.fetchone()[0]}")
                        
                        # Probar con JSON con comillas escapadas
                        test_json = '{"test": "value"}'
                        cursor.execute("SELECT ISJSON(?)", [test_json])
                        print(f"  ISJSON('{{\"test\": \"value\"}}'): {cursor.fetchone()[0]}")
                        
                        # Verificar si hay caracteres problemáticos
                        print(f"  Caracteres especiales en JSON:")
                        for char in json_str[:100]:
                            if ord(char) > 127:
                                print(f"    Carácter Unicode U+{ord(char):04X}: {repr(char)}")
                        
                except Exception as e:
                    print(f"  Error ejecutando ISJSON: {e}")
                    
    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=== Prueba ISJSON con datos reales ===")
    test_isjson()