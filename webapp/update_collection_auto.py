#!/usr/bin/env python
"""
Script para actualizar automáticamente la colección 'propiedades_propifai' con SQL correcto.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from intelligence.models import IntelligenceCollection

def main():
    # Buscar la colección
    collection_id = 'b899d903-5a14-4b23-b567-6bf15aa5f5b9'
    
    try:
        collection = IntelligenceCollection.objects.get(id=collection_id)
        print(f"Colección encontrada: {collection.name}")
        print(f"SQL anterior:\n{collection.source_sql[:500]}...")
        
        # Nuevo SQL corregido
        new_sql = """
SELECT
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
    p.availability_status as condicion,
    p.created_at as fecha_creacion,
    1 as es_propify,
    CONCAT_WS(' ', 
        COALESCE(p.title, ''),
        COALESCE(p.description, ''),
        COALESCE(p.real_address, ''),
        COALESCE(p.district, ''),
        COALESCE(p.availability_status, '')
    ) as contenido_embedding
FROM properties p
WHERE p.is_active = 1
"""
        
        # Actualizar la colección
        collection.source_sql = new_sql
        collection.embedding_fields = ['titulo', 'descripcion', 'direccion', 'distrito', 'condicion']
        collection.save()
        
        print("\n✅ Colección actualizada exitosamente")
        print(f"   Nuevo SQL guardado (longitud: {len(new_sql)} caracteres)")
        print(f"   Campos para embedding: {collection.embedding_fields}")
        
        # Verificar que el SQL ahora es correcto
        collection.refresh_from_db()
        print(f"\n--- Verificación ---")
        print(f"Tabla referenciada: {'properties' in collection.source_sql}")
        print(f"Campos actualizados: {collection.embedding_fields}")
        
    except IntelligenceCollection.DoesNotExist:
        print(f"Colección con ID {collection_id} no encontrada")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()