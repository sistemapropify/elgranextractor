#!/usr/bin/env python
"""
Script para probar ISJSON con el JSON generado por _serialize_row_dict
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

def test_json_with_isjson():
    """Probar JSON con ISJSON de SQL Server"""
    
    try:
        # Obtener conexión a la base de datos propifai
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
                    p.availability_status as condicion,
                    p.price as precio,
                    'PEN' as moneda,
                    p.built_area as area_construida,
                    p.land_area as area_total,
                    p.bedrooms as habitaciones,
                    p.bathrooms as banos,
                    p.garage_spaces as estacionamientos,
                    p.created_at as fecha_creacion,
                    1 as es_propify
                FROM properties p
                WHERE p.is_active = 1
            """)
            
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()
            
            if row:
                row_dict = dict(zip(columns, row))
                print("Datos originales de la fila:")
                for key, value in row_dict.items():
                    print(f"  {key}: {repr(value)} ({type(value).__name__})")
                
                # Serializar
                serialized = RAGService._serialize_row_dict(row_dict)
                print("\nDatos serializados:")
                for key, value in serialized.items():
                    print(f"  {key}: {repr(value)} ({type(value).__name__})")
                
                # Convertir a JSON
                json_str = json.dumps(serialized, ensure_ascii=False)
                print(f"\nJSON generado (completo):")
                print(json_str)
                
                # Probar ISJSON
                print("\nProbando ISJSON en SQL Server...")
                cursor.execute("SELECT ISJSON(?)", [json_str])
                is_json_result = cursor.fetchone()[0]
                print(f"ISJSON devuelve: {is_json_result}")
                
                if is_json_result == 0:
                    print("ERROR: JSON no válido para SQL Server")
                    
                    # Probar con JSON más simple
                    test_cases = [
                        ('{}', 'JSON vacío'),
                        ('{"test": "value"}', 'JSON simple'),
                        ('{"test": 123}', 'JSON con número'),
                        ('{"test": 123.45}', 'JSON con decimal'),
                        ('{"test": null}', 'JSON con null'),
                        ('{"test": true}', 'JSON con true'),
                    ]
                    
                    for test_json, desc in test_cases:
                        cursor.execute("SELECT ISJSON(?)", [test_json])
                        result = cursor.fetchone()[0]
                        print(f"  {desc}: ISJSON = {result}")
                    
                    # Verificar problemas específicos en nuestro JSON
                    print("\nBuscando problemas en nuestro JSON:")
                    
                    # 1. Verificar si hay comillas simples
                    if "'" in json_str:
                        print("  ❌ Contiene comillas simples")
                    
                    # 2. Verificar si hay saltos de línea
                    if '\n' in json_str:
                        print("  ❌ Contiene saltos de línea")
                    
                    # 3. Verificar caracteres de control
                    control_chars = [chr(i) for i in range(32) if chr(i) not in '\t\n\r']
                    for char in control_chars:
                        if char in json_str:
                            print(f"  ❌ Contiene carácter de control: {repr(char)}")
                    
                    # 4. Probar con ensure_ascii=True
                    print("\nProbando con ensure_ascii=True...")
                    json_str_ascii = json.dumps(serialized, ensure_ascii=True)
                    cursor.execute("SELECT ISJSON(?)", [json_str_ascii])
                    result_ascii = cursor.fetchone()[0]
                    print(f"  ISJSON con ensure_ascii=True: {result_ascii}")
                    
                    # 5. Probar eliminando campos problemáticos
                    print("\nProbando con campos mínimos...")
                    simple_dict = {'id': 1, 'test': 'value'}
                    simple_json = json.dumps(simple_dict)
                    cursor.execute("SELECT ISJSON(?)", [simple_json])
                    result_simple = cursor.fetchone()[0]
                    print(f"  ISJSON con dict simple: {result_simple}")
                    
                else:
                    print("✅ JSON válido para SQL Server")
                    
                    # Probar insertar en la tabla
                    print("\nProbando inserción en tabla intelligence_documents...")
                    try:
                        # Necesitamos una colección para la prueba
                        from intelligence.models import IntelligenceCollection
                        collection = IntelligenceCollection.objects.filter(
                            name__icontains='propiedades_propifai',
                            is_active=True
                        ).first()
                        
                        if collection:
                            # Crear documento de prueba
                            from intelligence.models import IntelligenceDocument
                            import uuid
                            
                            source_id = str(uuid.uuid4())
                            content = "Test content"
                            content_hash = RAGService.calculate_content_hash(content)
                            embedding = RAGService.generate_embedding(content)
                            
                            print(f"  Creando documento con metadata_json...")
                            doc = IntelligenceDocument.objects.create(
                                collection=collection,
                                source_id=source_id,
                                content=content,
                                content_hash=content_hash,
                                embedding=embedding,
                                metadata_json=json_str
                            )
                            print(f"  ✅ Documento creado exitosamente (ID: {doc.id})")
                            
                            # Limpiar
                            doc.delete()
                            print(f"  Documento eliminado")
                        else:
                            print("  No se encontró colección para prueba")
                            
                    except Exception as e:
                        print(f"  ❌ Error insertando documento: {e}")
                        
    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=== Prueba ISJSON con JSON generado ===")
    test_json_with_isjson()