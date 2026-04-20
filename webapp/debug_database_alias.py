#!/usr/bin/env python
"""
Script para depurar el problema con database_alias.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from intelligence.services.rag import RAGService
from intelligence.services.schema_discovery import SchemaDiscoveryService

def test_database_alias_flow():
    """Prueba el flujo completo con database_alias='propifai'."""
    print("=== Probando flujo con database_alias='propifai' ===")
    
    # 1. Llamar directamente a RAGService.get_available_tables
    print("\n1. Llamando a RAGService.get_available_tables(schema='dbo', database_alias='propifai', force_refresh=True)")
    tables = RAGService.get_available_tables(schema='dbo', database_alias='propifai', force_refresh=True)
    print(f"   Resultado: {len(tables)} tablas")
    if tables:
        print(f"   Primeras 5 tablas: {tables[:5]}")
    
    # 2. Llamar directamente a SchemaDiscoveryService.list_tables
    print("\n2. Llamando a SchemaDiscoveryService.list_tables(schema='dbo', database_alias='propifai', force_refresh=True)")
    tables2 = SchemaDiscoveryService.list_tables(schema='dbo', database_alias='propifai', force_refresh=True)
    print(f"   Resultado: {len(tables2)} tablas")
    if tables2:
        print(f"   Primeras 5 tablas: {tables2[:5]}")
    
    # 3. Comparar con database_alias='default'
    print("\n3. Comparando con database_alias='default'")
    tables_default = RAGService.get_available_tables(schema='dbo', database_alias='default', force_refresh=False)
    print(f"   Tablas en 'default': {len(tables_default)}")
    
    # 4. Verificar si son las mismas tablas
    if tables and tables_default:
        if set(tables) == set(tables_default):
            print("   ⚠️  ADVERTENCIA: Las tablas son IDÉNTICAS (mismo conjunto)")
        else:
            print("   ✓ Las tablas son DIFERENTES (conjuntos distintos)")
            
            # Encontrar diferencias
            only_in_propifai = set(tables) - set(tables_default)
            only_in_default = set(tables_default) - set(tables)
            
            if only_in_propifai:
                print(f"   Tablas solo en 'propifai' (primeras 5): {list(only_in_propifai)[:5]}")
            if only_in_default:
                print(f"   Tablas solo en 'default' (primeras 5): {list(only_in_default)[:5]}")

def test_cache_behavior():
    """Prueba el comportamiento del cache."""
    print("\n=== Probando comportamiento del cache ===")
    
    # Limpiar cache primero
    print("1. Limpiando cache...")
    SchemaDiscoveryService._tables_cache = None
    SchemaDiscoveryService._tables_cache_timestamp = None
    
    # Primera llamada (debería consultar BD)
    print("2. Primera llamada con 'propifai' (debería consultar BD)")
    tables1 = SchemaDiscoveryService.list_tables(schema='dbo', database_alias='propifai', force_refresh=False)
    print(f"   Resultado: {len(tables1)} tablas")
    
    # Segunda llamada (debería usar cache)
    print("3. Segunda llamada con 'propifai' (debería usar cache)")
    tables2 = SchemaDiscoveryService.list_tables(schema='dbo', database_alias='propifai', force_refresh=False)
    print(f"   Resultado: {len(tables2)} tablas")
    
    # Tercera llamada con 'default' (debería consultar BD diferente)
    print("4. Tercera llamada con 'default' (debería consultar BD diferente)")
    tables3 = SchemaDiscoveryService.list_tables(schema='dbo', database_alias='default', force_refresh=False)
    print(f"   Resultado: {len(tables3)} tablas")
    
    # Verificar cache keys
    print("\n5. Estado del cache:")
    if SchemaDiscoveryService._tables_cache:
        for key in SchemaDiscoveryService._tables_cache.keys():
            print(f"   Cache key: '{key}' -> {len(SchemaDiscoveryService._tables_cache[key])} tablas")

if __name__ == '__main__':
    print("Iniciando depuración de database_alias...")
    test_database_alias_flow()
    test_cache_behavior()
    print("\nDepuración completada.")