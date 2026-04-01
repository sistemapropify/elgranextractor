"""
Script para corregir el campo id_propiedad con los valores de identificador_externo.
"""

import os
import sys

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from django.db import connection
    
    print("=== CORRECCIÓN DE CAMPO id_propiedad ===")
    print("\nProblema identificado:")
    print("El campo 'id_propiedad' (id_de_la_propiedad en la tabla) debe contener")
    print("los valores de 'identificador_externo' del Excel.")
    
    # Verificar estado actual
    print("\n1. Verificando estado actual en la base de datos:")
    
    with connection.cursor() as cursor:
        # Contar registros
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        total = cursor.fetchone()[0]
        print(f"   Total de registros: {total}")
        
        # Verificar cuántos tienen id_propiedad vacío
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN id_propiedad IS NULL OR id_propiedad = '' THEN 1 ELSE 0 END) as vacios,
                SUM(CASE WHEN id_propiedad IS NOT NULL AND id_propiedad != '' THEN 1 ELSE 0 END) as con_valor
            FROM ingestas_propiedadraw
        """)
        row = cursor.fetchone()
        print(f"   Registros con id_propiedad vacío: {row[1]}")
        print(f"   Registros con id_propiedad con valor: {row[2]}")
        
        # Verificar cuántos tienen identificador_externo
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN identificador_externo IS NULL OR identificador_externo = '' THEN 1 ELSE 0 END) as vacios,
                SUM(CASE WHEN identificador_externo IS NOT NULL AND identificador_externo != '' THEN 1 ELSE 0 END) as con_valor
            FROM ingestas_propiedadraw
        """)
        row = cursor.fetchone()
        print(f"   Registros con identificador_externo vacío: {row[1]}")
        print(f"   Registros con identificador_externo con valor: {row[2]}")
        
        # Verificar cuántos tienen ambos campos
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ingestas_propiedadraw 
            WHERE (id_propiedad IS NULL OR id_propiedad = '')
            AND (identificador_externo IS NOT NULL AND identificador_externo != '')
        """)
        row = cursor.fetchone()
        print(f"\n   Registros que se pueden corregir (id_propiedad vacío, identificador_externo con valor): {row[0]}")
        
        # Mostrar ejemplos
        if row[0] > 0:
            print("\n   Ejemplos de registros a corregir:")
            cursor.execute("""
                SELECT TOP 5 
                    id, 
                    identificador_externo,
                    id_propiedad
                FROM ingestas_propiedadraw 
                WHERE (id_propiedad IS NULL OR id_propiedad = '')
                AND (identificador_externo IS NOT NULL AND identificador_externo != '')
                ORDER BY id
            """)
            for r in cursor.fetchall():
                print(f"      ID: {r[0]}, Identificador Externo: '{r[1]}', ID Propiedad: '{r[2]}'")
    
    # Preguntar si se desea corregir
    print("\n2. ¿Desea corregir los datos?")
    print("   Esta operación actualizará id_propiedad con los valores de identificador_externo")
    print("   donde id_propiedad esté vacío.")
    
    respuesta = input("\n   ¿Continuar? (s/n): ").strip().lower()
    
    if respuesta == 's':
        print("\n3. Ejecutando corrección...")
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE ingestas_propiedadraw 
                SET id_propiedad = identificador_externo
                WHERE (id_propiedad IS NULL OR id_propiedad = '')
                AND (identificador_externo IS NOT NULL AND identificador_externo != '')
            """)
            filas_afectadas = cursor.rowcount
            print(f"   ✓ {filas_afectadas} registros actualizados.")
            
            # Verificar resultado
            cursor.execute("""
                SELECT COUNT(*) 
                FROM ingestas_propiedadraw 
                WHERE (id_propiedad IS NULL OR id_propiedad = '')
            """)
            row = cursor.fetchone()
            print(f"   Registros con id_propiedad vacío después: {row[0]}")
            
        print("\n   ✓ Corrección completada.")
    else:
        print("\n   ✗ Operación cancelada.")
    
    print("\n4. Solución permanente:")
    print("   Para evitar este problema en futuras importaciones, modificar")
    print("   webapp/ingestas/management/commands/importar_excel_propiedadraw.py")
    print("\n   Cambiar el mapeo en la línea 114:")
    print("   DE: 'ID de la Propiedad': 'id_propiedad'")
    print("   A: 'identificador-externo': 'id_propiedad'")
    print("\n   O agregar un mapeo adicional:")
    print("   'identificador-externo': ['identificador_externo', 'id_propiedad']")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()