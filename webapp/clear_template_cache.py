#!/usr/bin/env python
"""
Script para limpiar el cache de templates de Django
"""
import os
import sys
import shutil
import django
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

# Limpiar directorios de cache
cache_dirs = [
    os.path.join(settings.BASE_DIR, '__pycache__'),
    os.path.join(settings.BASE_DIR, 'market_analysis', '__pycache__'),
    os.path.join(settings.BASE_DIR, 'market_analysis', 'templates', '__pycache__'),
    os.path.join(settings.BASE_DIR, 'market_analysis', 'templates', 'market_analysis', '__pycache__'),
]

print("Limpiando cache de templates de Django...")
for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print(f"  ✓ Eliminado: {cache_dir}")
        except Exception as e:
            print(f"  ✗ Error eliminando {cache_dir}: {e}")

# También limpiar .pyc files
for root, dirs, files in os.walk(settings.BASE_DIR):
    for file in files:
        if file.endswith('.pyc'):
            try:
                os.remove(os.path.join(root, file))
                print(f"  ✓ Eliminado .pyc: {os.path.join(root, file)}")
            except:
                pass

print("\nCache limpiado. Reinicie el servidor Django.")
print("Para forzar recarga de templates, también puede ejecutar:")
print("  py manage.py shell -c \"from django.template import loader; loader.template_source_loaders = None\"")