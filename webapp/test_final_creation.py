#!/usr/bin/env python
"""
Script final para probar la creación de colección con campos reales de la tabla properties.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.services.schema_discovery import SchemaDiscoveryService

def test_final_creation():
    """Prueba final de creación de colección con campos reales."""
    print("=== Prueba Final de Creación de Colección ===\n")
    
    try:
        # Primero, obtener los campos reales de la tabla properties
        print("1. Obteniendo campos reales de la tabla 'properties'...")
        schema_analysis = SchemaDiscoveryService.analyze_table_schema(
            table_name='properties',
            schema='dbo',
            database_alias='propifai'
        )
        
        if not schema_analysis.get('exists', False):
            print(f"ERROR: No se pudo analizar la tabla: {schema_analysis.get('error', 'Error desconocido')}")
            return
        
        columns = schema_analysis.get('columns', [])
        print(f"   OK: Encontradas {len(columns)} columnas en la tabla 'properties'")
        
        # Mostrar algunas columnas para referencia
        print("\n   Primeras 10 columnas:")
        for i, col in enumerate(columns[:10], 1):
            print(f"     {i}. {col.get('name', 'N/A')} ({col.get('type', 'N/A')})")
        
        if len(columns) > 10:
            print(f"     ... y {len(columns) - 10} columnas más")
        
        # Buscar campos adecuados para diferentes propósitos
        text_fields = []
        display_fields = []
        filter_fields = []
        
        for col in columns:
            col_name = col.get('name', '').lower()
            col_type = col.get('type', '').lower()
            
            # Campos de texto para embedding
            if any(text_type in col_type for text_type in ['char', 'text', 'varchar', 'nvarchar']):
                if any(keyword in col_name for keyword in ['title', 'description', 'name', 'detail', 'note', 'comment']):
                    text_fields.append(col.get('name'))
            
            # Campos para visualización
            if any(keyword in col_name for keyword in ['code', 'title', 'price', 'type', 'status', 'location', 'address']):
                display_fields.append(col.get('name'))
            
            # Campos para filtrado
            if any(keyword in col_name for keyword in ['type', 'status', 'district', 'zone', 'category', 'condition']):
                filter_fields.append(col.get('name'))
        
        # Si no encontramos campos de texto, usar algunos por defecto
        if not text_fields:
            text_fields = ['title', 'description']
            print("\n   ADVERTENCIA: No se encontraron campos de texto ideales, usando campos por defecto")
        
        # Limitar a 3 campos máximo para cada categoría
        text_fields = text_fields[:3]
        display_fields = display_fields[:5]
        filter_fields = filter_fields[:3]
        
        print(f"\n2. Campos seleccionados:")
        print(f"   - Para embedding (búsqueda semántica): {text_fields}")
        print(f"   - Para visualización: {display_fields}")
        print(f"   - Para filtrado: {filter_fields}")
        
        # Verificar que los campos existan
        all_column_names = [col.get('name') for col in columns]
        missing_fields = []
        
        for field_list, purpose in [(text_fields, 'embedding'), (display_fields, 'display'), (filter_fields, 'filter')]:
            for field in field_list:
                if field not in all_column_names:
                    missing_fields.append((field, purpose))
        
        if missing_fields:
            print(f"\n   ⚠️ Advertencia: Algunos campos no existen en la tabla:")
            for field, purpose in missing_fields:
                print(f"     - '{field}' para {purpose}")
            
            # Filtrar campos que sí existen
            text_fields = [f for f in text_fields if f in all_column_names]
            display_fields = [f for f in display_fields if f in all_column_names]
            filter_fields = [f for f in filter_fields if f in all_column_names]
            
            print(f"\n   ✓ Campos válidos después de filtrar:")
            print(f"     - Embedding: {text_fields}")
            print(f"     - Display: {display_fields}")
            print(f"     - Filter: {filter_fields}")
        
        # Crear colección de prueba
        print(f"\n3. Creando colección de prueba...")
        name = "Propiedades Test " + str(int(os.times().elapsed))
        
        success, message, collection = RAGService.create_collection_dynamic(
            name=name,
            table_name='properties',
            embedding_fields=text_fields,
            display_fields=display_fields,
            filter_fields=filter_fields,
            access_level=2,
            description="Colección de prueba para propiedades de dbpropify",
            schema='dbo',
            database_alias='propifai'
        )
        
        print(f"\n4. Resultado:")
        print(f"   - success: {success}")
        print(f"   - message: {message}")
        
        if success and collection:
            print(f"   - collection_id: {collection.id}")
            print(f"   - collection_name: {collection.name}")
            print(f"   - table_name: {collection.table_name}")
            print(f"   - database: propifai")
            print(f"   - embedding_fields: {collection.embedding_fields}")
            print(f"   - display_fields: {collection.display_fields}")
            print(f"   - filter_fields: {collection.filter_fields}")
            
            # Limpiar: eliminar la colección de prueba
            print(f"\n5. Limpiando colección de prueba...")
            collection.delete()
            print(f"   ✓ Colección eliminada exitosamente")
        else:
            print(f"   - error: {message}")
            
            # Si el error es por campos que no existen, mostrar campos disponibles
            if "no existe en la tabla" in message:
                print(f"\n   Campos disponibles en la tabla 'properties':")
                for i, col in enumerate(columns[:20], 1):
                    print(f"     {i}. {col.get('name', 'N/A')} ({col.get('type', 'N/A')})")
                
                if len(columns) > 20:
                    print(f"     ... y {len(columns) - 20} columnas más")
        
        print(f"\n=== Prueba completada ===")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_final_creation()