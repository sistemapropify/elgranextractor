#!/usr/bin/env python
"""
Script para verificar la colección 'propiedades_propifai' y su SQL.
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
    # Buscar la colección por ID o nombre
    collection_id = 'b899d903-5a14-4b23-b567-6bf15aa5f5b9'
    collection_name = 'propiedades_propifai'
    
    try:
        # Intentar por ID
        collection = IntelligenceCollection.objects.get(id=collection_id)
        print(f"Colección encontrada por ID: {collection.name}")
    except IntelligenceCollection.DoesNotExist:
        try:
            # Intentar por nombre
            collection = IntelligenceCollection.objects.get(name=collection_name)
            print(f"Colección encontrada por nombre: {collection.name}")
        except IntelligenceCollection.DoesNotExist:
            print(f"No se encontró colección con ID {collection_id} ni nombre {collection_name}")
            return
    
    print(f"\nID: {collection.id}")
    print(f"Nombre: {collection.name}")
    print(f"Descripción: {collection.description}")
    print(f"Nivel de acceso: {collection.access_level}")
    print(f"Activa: {collection.is_active}")
    print(f"\nSQL actual:")
    print("-" * 80)
    print(collection.source_sql)
    print("-" * 80)
    print(f"\nCampos para embedding: {collection.embedding_fields}")
    print(f"Última sincronización: {collection.last_sync_at}")
    print(f"Registros en última sincro: {collection.last_sync_count}")
    
    # Verificar si el SQL hace referencia a tabla incorrecta
    if 'propifai_propiedad' in collection.source_sql:
        print("\n⚠️  ADVERTENCIA: El SQL hace referencia a 'propifai_propiedad' que no existe.")
        print("   La tabla correcta para propiedades Propifai es 'propifai_propiedad'?")
        print("   Revisando modelos Django...")
        
        from django.apps import apps
        from django.db import connection
        
        # Listar tablas en la base de datos
        with connection.cursor() as cursor:
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
            tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\nTablas en la base de datos:")
        for table in sorted(tables):
            if 'propifai' in table.lower() or 'propiedad' in table.lower():
                print(f"  - {table}")
        
        # Verificar modelo PropifaiProperty
        from propifai.models import PropifaiProperty
        print(f"\nModelo PropifaiProperty._meta.db_table: {PropifaiProperty._meta.db_table}")
        
        # Verificar si hay datos en la tabla correcta
        count = PropifaiProperty.objects.count()
        print(f"PropifaiProperty.objects.count(): {count}")

if __name__ == '__main__':
    main()