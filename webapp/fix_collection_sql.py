#!/usr/bin/env python
"""
Script simple para actualizar la colección sin emojis.
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
    collection_id = 'b899d903-5a14-4b23-b567-6bf15aa5f5b9'
    
    try:
        collection = IntelligenceCollection.objects.get(id=collection_id)
        print("Coleccion encontrada:", collection.name)
        
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
        
        # Actualizar
        collection.source_sql = new_sql
        collection.embedding_fields = ['titulo', 'descripcion', 'direccion', 'distrito', 'condicion']
        collection.save()
        
        print("OK - Coleccion actualizada")
        print("Nuevo SQL usa tabla: properties")
        print("Campos embedding:", collection.embedding_fields)
        
    except Exception as e:
        print("Error:", str(e))

if __name__ == '__main__':
    main()