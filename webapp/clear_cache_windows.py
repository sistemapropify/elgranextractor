#!/usr/bin/env python
"""
Script simple para limpiar cache de templates de Django en Windows
"""
import os
import shutil

print("Limpiando cache de templates de Django...")

# Directorios base
base_dir = os.path.dirname(os.path.abspath(__file__))

# Directorios de cache a limpiar
cache_dirs = [
    os.path.join(base_dir, '__pycache__'),
    os.path.join(base_dir, 'market_analysis', '__pycache__'),
    os.path.join(base_dir, 'market_analysis', 'templates', '__pycache__'),
    os.path.join(base_dir, 'market_analysis', 'templates', 'market_analysis', '__pycache__'),
    os.path.join(base_dir, 'templates', '__pycache__'),
]

# También buscar y eliminar todos los .pyc files
pyc_count = 0
for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith('.pyc'):
            try:
                os.remove(os.path.join(root, file))
                pyc_count += 1
            except:
                pass

# Eliminar directorios de cache
dir_count = 0
for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            rel_path = os.path.relpath(cache_dir, base_dir)
            print(f"  [OK] Eliminado: {rel_path}")
            dir_count += 1
        except Exception as e:
            print(f"  [ERROR] Error eliminando {cache_dir}: {e}")

print(f"\nResumen:")
print(f"  - Directorios de cache eliminados: {dir_count}")
print(f"  - Archivos .pyc eliminados: {pyc_count}")
print("\nCache limpiado. Reinicie el servidor Django.")

# Forzar recarga de templates
print("\nPara forzar recarga completa:")
print("1. Detener todos los servidores Django")
print("2. Ejecutar: py manage.py shell -c \"from django.template import loader; loader.template_source_loaders = None\"")
print("3. Reiniciar el servidor")