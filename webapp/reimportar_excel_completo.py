#!/usr/bin/env python
"""
Script para borrar todos los registros de PropiedadRaw y reimportar desde el Excel corregido.
"""

import os
import sys
import django
from django.core.management import call_command
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== REIMPORTACIÓN COMPLETA DE PROPIEDADES RAW ===\n")
    
    # 1. Verificar estado actual
    print("1. Verificando estado actual de la tabla...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        print(f"   Registros actuales en PropiedadRaw: {count}")
    
    # 2. Borrar todos los registros
    print("\n2. Borrando todos los registros de PropiedadRaw...")
    try:
        with connection.cursor() as cursor:
            # Usar TRUNCATE para SQL Server
            cursor.execute("TRUNCATE TABLE ingestas_propiedadraw")
            print("   ✓ Tabla truncada exitosamente")
    except Exception as e:
        print(f"   ✗ Error al truncar tabla: {e}")
        print("   Intentando con DELETE...")
        try:
            from ingestas.models import PropiedadRaw
            PropiedadRaw.objects.all().delete()
            print("   ✓ Registros eliminados con DELETE")
        except Exception as e2:
            print(f"   ✗ Error con DELETE: {e2}")
            return
    
    # 3. Verificar que la tabla esté vacía
    print("\n3. Verificando que la tabla esté vacía...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        if count == 0:
            print("   ✓ Tabla vacía confirmada")
        else:
            print(f"   ✗ Tabla todavía tiene {count} registros")
    
    # 4. Importar desde Excel corregido
    print("\n4. Importando desde Excel 'propiedadesraw_corregido (2).xlsx'...")
    excel_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'requerimientos', 
        'data', 
        'propiedadesraw_corregido (2).xlsx'
    )
    
    # Verificar que el archivo existe
    if not os.path.exists(excel_path):
        print(f"   ✗ Archivo no encontrado: {excel_path}")
        print("   Buscando alternativas...")
        # Buscar archivo en otras ubicaciones
        posibles_rutas = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'propiedadesraw_corregido (2).xlsx'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'propiedadesraw_corregido (2).xlsx'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requerimientos', 'propiedadesraw_corregido (2).xlsx'),
            'D:\\proyectos\\prometeo\\webapp\\requerimientos\\data\\propiedadesraw_corregido (2).xlsx'
        ]
        
        for ruta in posibles_rutas:
            if os.path.exists(ruta):
                excel_path = ruta
                print(f"   ✓ Archivo encontrado en: {ruta}")
                break
        else:
            print("   ✗ No se encontró el archivo Excel. Por favor, verifica la ubicación.")
            print("   El archivo debe estar en: webapp/requerimientos/data/propiedadesraw_corregido (2).xlsx")
            return
    
    print(f"   ✓ Archivo encontrado: {excel_path}")
    
    # 5. Ejecutar comando de importación
    try:
        print("   Ejecutando comando de importación...")
        # Usar el comando de importación existente
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'importar_excel_propiedadraw', excel_path])
        print("   ✓ Comando de importación ejecutado")
    except Exception as e:
        print(f"   ✗ Error al ejecutar comando: {e}")
        print("   Intentando importación directa...")
        # Intentar importación directa
        try:
            from ingestas.management.commands.importar_excel_propiedadraw import Command
            cmd = Command()
            cmd.handle(archivo=excel_path)
            print("   ✓ Importación directa exitosa")
        except Exception as e2:
            print(f"   ✗ Error en importación directa: {e2}")
            return
    
    # 6. Verificar importación
    print("\n5. Verificando importación...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        count = cursor.fetchone()[0]
        print(f"   Registros importados: {count}")
        
        # Verificar campos condicion y propiedad_verificada
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN condicion IS NOT NULL THEN 1 END) as con_condicion,
                COUNT(CASE WHEN propiedad_verificada IS NOT NULL THEN 1 END) as con_verificada
            FROM ingestas_propiedadraw
        """)
        stats = cursor.fetchone()
        print(f"   Registros con 'condicion': {stats[0]}")
        print(f"   Registros con 'propiedad_verificada': {stats[1]}")
        
        # Mostrar algunos ejemplos
        cursor.execute("SELECT TOP 5 id, condicion, propiedad_verificada FROM ingestas_propiedadraw")
        ejemplos = cursor.fetchall()
        if ejemplos:
            print("\n   Primeros 5 registros (id, condicion, propiedad_verificada):")
            for ej in ejemplos:
                print(f"     {ej}")
    
    print("\n=== REIMPORTACIÓN COMPLETADA ===")
    print("\nRecomendaciones:")
    print("1. Reinicia el servidor Django si estaba corriendo")
    print("2. Verifica que los campos se muestren correctamente en:")
    print("   - Admin: /admin/ingestas/propiedadraw/")
    print("   - Portal: /ingestas/propiedades/")
    print("   - Detalles: /ingestas/propiedad/<id>/")
    print("\n3. Si los campos aún no aparecen, verifica que:")
    print("   - Las columnas existen en la base de datos (ejecutar verificar_estado_final.py)")
    print("   - El Excel tiene datos en las columnas 'condicion' y 'propiedad_verificada'")

if __name__ == '__main__':
    main()