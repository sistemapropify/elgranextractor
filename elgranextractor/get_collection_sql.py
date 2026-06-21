#!/usr/bin/env python
"""
Obtener SQL de la colección
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection

def get_collection_sql():
    """Obtener SQL de la colección"""
    
    try:
        collection = IntelligenceCollection.objects.get(id='491d87ba-5ffe-4d0e-826f-a99d44652181')
        print(f"Colección: {collection.name}")
        print(f"SQL:\n{collection.source_sql}")
        print(f"\nCampos embedding: {collection.embedding_fields}")
        print(f"Nivel acceso: {collection.access_level}")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    get_collection_sql()