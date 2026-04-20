#!/usr/bin/env python
"""
Script para probar el código ACTUAL que está en disco (no cacheado).
"""
import os
import sys
import importlib

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Forzar recarga del módulo
import intelligence.services.schema_discovery
importlib.reload(intelligence.services.schema_discovery)

from intelligence.services.schema_discovery import SchemaDiscoveryService

print("=== Probando código ACTUAL en disco ===")

# Limpiar cache primero
print("1. Limpiando cache...")
SchemaDiscoveryService._tables_cache = None
SchemaDiscoveryService._tables_cache_timestamp = None

# Probar con 'propifai'
print("\n2. Probando con database_alias='propifai'...")
try:
    tables = SchemaDiscoveryService.list_tables(schema='dbo', database_alias='propifai', force_refresh=False)
    print(f"   Resultado: {len(tables)} tablas")
    if tables:
        print(f"   Primeras 5 tablas: {tables[:5]}")
        
        # Verificar si son tablas de propifai
        propifai_tables = ['agency_config', 'canal_leads', 'properties', 'requirements', 'users']
        found = sum(1 for table in tables if table in propifai_tables)
        print(f"   Tablas de propifai encontradas: {found}/5")
        
        if found > 0:
            print("   ✓ El código DEVUELVE tablas de propifai")
        else:
            print("   ✗ El código NO devuelve tablas de propifai")
except Exception as e:
    print(f"   Error: {e}")

# Probar con 'default'
print("\n3. Probando con database_alias='default'...")
try:
    tables = SchemaDiscoveryService.list_tables(schema='dbo', database_alias='default', force_refresh=False)
    print(f"   Resultado: {len(tables)} tablas")
    if tables:
        print(f"   Primeras 5 tablas: {tables[:5]}")
except Exception as e:
    print(f"   Error: {e}")

print("\n=== Prueba completada ===")