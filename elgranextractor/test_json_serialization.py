#!/usr/bin/env python
"""
Script para probar la serialización JSON
"""
import os
import sys
import django
import json
import decimal
import datetime

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from django.db import connections

def test_serialization():
    """Probar serialización de datos de ejemplo"""
    
    # Datos de ejemplo similares a los que vendrían de la base de datos
    row_dict = {
        'id': 1,
        'titulo': 'Casa en Cayma',
        'descripcion': 'Hermosa casa con vista',
        'direccion': 'Av. Ejemplo 123',
        'distrito': 'Cayma',
        'condicion': 'Nueva',
        'precio': decimal.Decimal('250000.50'),
        'area': decimal.Decimal('150.75'),
        'fecha_creacion': datetime.datetime(2024, 1, 15, 10, 30, 0),
        'fecha_actualizacion': datetime.date(2024, 3, 20),
        'activo': True,
        'nulo': None
    }
    
    print("Diccionario original:")
    for key, value in row_dict.items():
        print(f"  {key}: {value} ({type(value).__name__})")
    
    print("\nSerializando con _serialize_row_dict...")
    serialized = RAGService._serialize_row_dict(row_dict)
    
    print("\nDiccionario serializado:")
    for key, value in serialized.items():
        print(f"  {key}: {value} ({type(value).__name__})")
    
    print("\nConvirtiendo a JSON...")
    json_str = json.dumps(serialized, ensure_ascii=False, indent=2)
    print(f"JSON resultante (primeros 500 chars):")
    print(json_str[:500])
    
    # Verificar si es JSON válido
    try:
        parsed_back = json.loads(json_str)
        print("\n✅ JSON parseado correctamente de vuelta")
    except Exception as e:
        print(f"\n❌ Error parseando JSON: {e}")
    
    # Probar con ISJSON de SQL Server (simulado)
    print("\n=== Probando con datos reales de la colección ===")
    
    try:
        # Obtener conexión a la base de datos propifai
        from django.db import connections
        conn = connections['propifai']
        
        with conn.cursor() as cursor:
            # Ejecutar consulta de la colección
            cursor.execute("""
                SELECT TOP 1
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
            row = cursor.fetchone()
            
            if row:
                row_dict_real = dict(zip(columns, row))
                print("\nDatos reales de la base de datos:")
                for key, value in row_dict_real.items():
                    print(f"  {key}: {value} ({type(value).__name__})")
                
                serialized_real = RAGService._serialize_row_dict(row_dict_real)
                json_str_real = json.dumps(serialized_real, ensure_ascii=False)
                
                print(f"\nJSON real (primeros 300 chars):")
                print(json_str_real[:300])
                
                # Verificar longitud
                print(f"\nLongitud del JSON: {len(json_str_real)} caracteres")
                
                # Probar si pasa ISJSON
                print("\nProbando ISJSON en SQL Server...")
                cursor.execute("SELECT ISJSON(?)", [json_str_real])
                is_json_result = cursor.fetchone()[0]
                print(f"ISJSON devuelve: {is_json_result} (1 = válido, 0 = inválido)")
                
                if is_json_result == 0:
                    print("⚠️  ADVERTENCIA: SQL Server no considera este JSON válido")
                    # Probar con string vacío
                    cursor.execute("SELECT ISJSON('{}')")
                    print(f"ISJSON('{{}}') devuelve: {cursor.fetchone()[0]}")
                    
    except Exception as e:
        print(f"Error obteniendo datos reales: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=== Prueba de serialización JSON ===")
    test_serialization()