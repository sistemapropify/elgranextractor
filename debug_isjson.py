#!/usr/bin/env python
"""
Debug: Probar ISJSON directamente con diferentes variantes del JSON
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

from django.db import connections

def debug_isjson():
    """Debug ISJSON problema"""
    
    print("DEBUG: Probando ISJSON con diferentes variantes")
    
    # JSON que estamos generando (copiado del output anterior)
    our_json = '{"id": 2, "titulo": "Casa En Campo Verde - Cerro Colorado", "descripcion": "Casa en Campo Verde - Cerro Colorado", "direccion": "Urb. Campo Verde - Cerro Colorado, Arequipa", "distrito": "4", "condicion": "sold", "precio": 299000.0, "moneda": "PEN", "area_construida": null, "area_total": null, "habitaciones": 5, "banos": 4, "estacionamientos": 1, "fecha_creacion": "2026-01-08 02:30:52", "es_propify": 1}'
    
    print(f"Nuestro JSON: {our_json[:100]}...")
    print(f"Longitud: {len(our_json)}")
    
    try:
        # Probar parseo en Python
        parsed = json.loads(our_json)
        print("✅ JSON válido en Python")
        
        # Conectar a base de datos
        conn = connections['default']  # Usar base de datos default (propiextractor)
        
        with conn.cursor() as cursor:
            # Probar ISJSON directamente con string literal
            print("\nProbando ISJSON con string literal...")
            
            # Probar diferentes variantes
            test_cases = [
                ("SELECT ISJSON('{}')", "JSON vacío"),
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
            
            # Ahora probar con parámetro (esto es lo que falla)
            print("\nProbando con parámetro (como lo hace Django)...")
            
            # Primero probar con JSON simple
            simple_json = '{"test": 1}'
            try:
                # Usar execute con parámetros
                cursor.execute("SELECT ISJSON(?)", (simple_json,))
                result = cursor.fetchone()[0]
                print(f"  JSON simple con parámetro: {result}")
            except Exception as e:
                print(f"  ERROR con parámetro: {e}")
            
            # Probar insertar directamente en la tabla
            print("\nProbando inserción directa en SQL...")
            
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
                    cursor.execute("INSERT INTO #test_json (metadata_json) VALUES (?)", (our_json,))
                    print("  ✅ Inserción exitosa en tabla temporal")
                except Exception as e:
                    print(f"  ❌ Error insertando: {e}")
                    
                    # Probar con JSON más simple
                    simple = '{"test": 1}'
                    try:
                        cursor.execute("INSERT INTO #test_json (metadata_json) VALUES (?)", (simple,))
                        print("  ✅ JSON simple insertado correctamente")
                    except Exception as e2:
                        print(f"  ❌ Error incluso con JSON simple: {e2}")
                
                # Limpiar
                cursor.execute("DROP TABLE #test_json")
                
            except Exception as e:
                print(f"  Error creando tabla temporal: {e}")
                
            # Verificar la restricción CHECK exacta
            print("\n=== Verificando restricción CHECK exacta ===")
            cursor.execute("""
                SELECT 
                    cc.CHECK_CLAUSE,
                    tc.TABLE_NAME,
                    tc.CONSTRAINT_NAME
                FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
                JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc 
                    ON cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                WHERE tc.TABLE_NAME = 'intelligence_documents'
                    AND tc.CONSTRAINT_TYPE = 'CHECK'
                    AND cc.CONSTRAINT_NAME LIKE '%metadata_json%'
            """)
            
            constraints = cursor.fetchall()
            for check_clause, table_name, constraint_name in constraints:
                print(f"  Tabla: {table_name}")
                print(f"  Restricción: {constraint_name}")
                print(f"  Cláusula CHECK: {check_clause}")
                
                # Probar la cláusula directamente
                if 'ISJSON' in check_clause:
                    # Extraer la expresión ISJSON
                    print(f"  Probando cláusula ISJSON...")
                    
                    # Probar con nuestro JSON usando la cláusula completa
                    test_sql = f"SELECT CASE WHEN {check_clause} THEN 1 ELSE 0 END"
                    print(f"  SQL: {test_sql}")
                    
                    # No podemos probar fácilmente con parámetros aquí...
                    
    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()

def test_manual_insert():
    """Probar inserción manual con diferentes formatos"""
    
    print("\n\n=== Probando inserción manual ===")
    
    try:
        conn = connections['default']
        
        with conn.cursor() as cursor:
            # Obtener un ID de colección
            cursor.execute("SELECT TOP 1 id FROM intelligence_collections WHERE is_active = 1")
            collection_row = cursor.fetchone()
            
            if collection_row:
                collection_id = collection_row[0]
                print(f"Usando collection_id: {collection_id}")
                
                # Probar diferentes formatos de JSON
                test_jsons = [
                    ('{"test": 1}', 'JSON mínimo'),
                    ('{"id": 1, "name": "test"}', 'JSON con campos básicos'),
                    ('{"id": 1, "price": 100.5}', 'JSON con decimal'),
                    ('{"id": 1, "date": "2024-01-01"}', 'JSON con fecha simple'),
                    ('{"id": 1, "date": "2024-01-01 12:30:45"}', 'JSON con fecha y hora'),
                    # Nuestro JSON completo
                    ('{"id": 2, "titulo": "Casa", "precio": 299000.0, "fecha": "2026-01-08 02:30:52"}', 'JSON similar al nuestro'),
                ]
                
                for json_str, desc in test_jsons:
                    print(f"\nProbando: {desc}")
                    print(f"  JSON: {json_str}")
                    
                    # Generar source_id único
                    import uuid
                    source_id = str(uuid.uuid4())[:8]
                    
                    try:
                        cursor.execute("""
                            INSERT INTO intelligence_documents 
                            (collection_id, source_id, content, content_hash, embedding, metadata_json, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                        """, (
                            collection_id,
                            source_id,
                            'Test content',
                            'hash123',
                            b'test',  # embedding dummy
                            json_str
                        ))
                        
                        print(f"  ✅ Inserción exitosa")
                        
                        # Limpiar
                        cursor.execute("DELETE FROM intelligence_documents WHERE source_id = ?", (source_id,))
                        
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
                        
                        # Si es error de CHECK constraint, mostrar más detalles
                        if 'CHECK constraint' in str(e):
                            print(f"    CHECK constraint falló para este JSON")
                            
                            # Probar ISJSON directamente
                            try:
                                cursor.execute("SELECT ISJSON(?)", (json_str,))
                                isjson_result = cursor.fetchone()[0]
                                print(f"    ISJSON devuelve: {isjson_result}")
                            except:
                                print(f"    No se pudo probar ISJSON")
            
    except Exception as e:
        print(f"Error en inserción manual: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_isjson()
    test_manual_insert()