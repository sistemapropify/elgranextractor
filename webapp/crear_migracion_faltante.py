#!/usr/bin/env python
"""
Script para crear la migración faltante para los campos 'condicion' y 'propiedad_verificada'.
"""

import os
import sys
import django
from django.core.management import call_command

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== CREANDO MIGRACIÓN FALTANTE ===\n")
    
    # Verificar migraciones actuales
    print("1. Verificando migraciones actuales...")
    from django.db.migrations.loader import MigrationLoader
    from django.db import connections, DEFAULT_DB_ALIAS
    
    loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])
    app_migrations = loader.graph.nodes.get('ingestas', {})
    
    print(f"Migraciones de 'ingestas' encontradas: {len(app_migrations)}")
    for migration in sorted(app_migrations.keys()):
        print(f"  - {migration}")
    
    # Crear nueva migración
    print("\n2. Creando nueva migración...")
    try:
        call_command('makemigrations', 'ingestas', '--name', 'add_condicion_propiedad_verificada', '--dry-run')
        print("  ✓ Migración se puede crear (dry-run exitoso)")
        
        # Crear migración real
        call_command('makemigrations', 'ingestas', '--name', 'add_condicion_propiedad_verificada')
        print("  ✓ Migración creada exitosamente")
        
        # Mostrar archivo creado
        migraciones_dir = os.path.join(os.path.dirname(__file__), 'ingestas', 'migrations')
        archivos = sorted([f for f in os.listdir(migraciones_dir) if f.endswith('.py') and f != '__init__.py'])
        if archivos:
            ultima_migracion = archivos[-1]
            print(f"  ✓ Archivo creado: ingestas/migrations/{ultima_migracion}")
            
            # Mostrar contenido
            with open(os.path.join(migraciones_dir, ultima_migracion), 'r') as f:
                contenido = f.read()
                print(f"\nContenido de la migración:\n{contenido[:500]}...")
    except Exception as e:
        print(f"  ✗ Error al crear migración: {e}")
    
    print("\n3. Aplicando migración...")
    try:
        call_command('migrate', 'ingestas', verbosity=0)
        print("  ✓ Migración aplicada exitosamente")
    except Exception as e:
        print(f"  ✗ Error al aplicar migración: {e}")
        print("  Puedes aplicar manualmente con: python manage.py migrate ingestas")
    
    print("\n=== INSTRUCCIONES ===")
    print("1. Si la migración se creó y aplicó, reinicia el servidor Django.")
    print("2. Verifica que las columnas ahora existen con 'verificar_columnas_simple.py'.")
    print("3. Accede a /admin/ingestas/propiedadraw/ para confirmar que el error desapareció.")

if __name__ == '__main__':
    main()