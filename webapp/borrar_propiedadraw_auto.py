#!/usr/bin/env python
"""
Script para borrar TODOS los registros de PropiedadRaw (versión automática).
Ejecuta el borrado sin confirmación interactiva.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== BORRADO AUTOMÁTICO DE REGISTROS DE PROPIEDADRAW ===\n")
    
    # 1. Contar registros actuales
    print("1. Contando registros actuales...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        print(f"   Registros actuales en PropiedadRaw: {count}")
    
    if count == 0:
        print("\n   La tabla ya está vacía. No hay nada que borrar.")
        return
    
    # 2. Confirmación automática (SI)
    print(f"\n2. Confirmación automática: BORRANDO {count} registros...")
    print("   Esta acción NO se puede deshacer.")
    
    # 3. Borrar registros
    print("\n3. Borrando registros...")
    try:
        with connection.cursor() as cursor:
            # Usar TRUNCATE para SQL Server (más rápido)
            cursor.execute("TRUNCATE TABLE ingestas_propiedadraw")
            print("   ✓ Tabla truncada exitosamente (TRUNCATE)")
    except Exception as e:
        print(f"   ✗ Error con TRUNCATE: {e}")
        print("   Intentando con DELETE...")
        try:
            from ingestas.models import PropiedadRaw
            deleted_count = PropiedadRaw.objects.all().delete()
            print(f"   ✓ Registros eliminados con DELETE: {deleted_count}")
        except Exception as e2:
            print(f"   ✗ Error con DELETE: {e2}")
            return
    
    # 4. Verificar
    print("\n4. Verificando borrado...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        if count == 0:
            print("   ✓ Tabla vacía confirmada")
        else:
            print(f"   ✗ Tabla todavía tiene {count} registros")
    
    print("\n=== BORRADO COMPLETADO ===")
    print("\nInstrucciones:")
    print("1. Para importar datos desde Excel, ejecuta:")
    print("   python manage.py importar_excel_propiedadraw webapp/requerimientos/data/propiedadesraw_corregido (2).xlsx")
    print("\n2. O ejecuta el script completo de reimportación:")
    print("   python reimportar_excel_completo.py")

if __name__ == '__main__':
    main()