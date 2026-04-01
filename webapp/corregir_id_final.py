"""
Script FINAL para corregir id_propiedad - Usa la conexión de Django del proyecto.
"""

import os
import sys

# Agregar el directorio actual al path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from django.db import connection
    
    print("CORRECCIÓN DE CAMPO id_propiedad")
    print("=" * 60)
    
    # Verificar estado actual
    print("\n1. VERIFICANDO ESTADO ACTUAL:")
    
    with connection.cursor() as cursor:
        # Total de registros
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        total = cursor.fetchone()[0]
        print(f"   Total de registros: {total}")
        
        # Registros con id_propiedad vacío
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE id_propiedad IS NULL OR id_propiedad = ''")
        vacios = cursor.fetchone()[0]
        print(f"   Registros con id_propiedad vacío: {vacios}")
        
        # Registros con identificador_externo
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE identificador_externo IS NOT NULL AND identificador_externo != ''")
        con_identificador = cursor.fetchone()[0]
        print(f"   Registros con identificador_externo: {con_identificador}")
        
        # Registros que se pueden corregir
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ingestas_propiedadraw 
            WHERE (id_propiedad IS NULL OR id_propiedad = '')
            AND (identificador_externo IS NOT NULL AND identificador_externo != '')
        """)
        corregibles = cursor.fetchone()[0]
        print(f"   Registros que se pueden corregir: {corregibles}")
        
        if corregibles == 0:
            print("\n   No hay registros para corregir.")
            print("\n   Posibles causas:")
            print("   - La tabla está vacía")
            print("   - identificador_externo también está vacío")
            print("   - id_propiedad ya tiene valores")
            
            # Mostrar más detalles
            if total > 0:
                print("\n   Detalles adicionales:")
                cursor.execute("SELECT TOP 3 id, identificador_externo, id_propiedad FROM ingestas_propiedadraw ORDER BY id")
                for row in cursor.fetchall():
                    print(f"      ID: {row[0]}, Identificador: '{row[1]}', ID Propiedad: '{row[2]}'")
            
            sys.exit(0)
    
    # Ejecutar corrección
    print(f"\n2. EJECUTANDO CORRECCIÓN DE {corregibles} REGISTROS...")
    
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
    print("\n3. VERIFICANDO RESULTADO:")
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE id_propiedad IS NULL OR id_propiedad = ''")
        vacios_despues = cursor.fetchone()[0]
        print(f"   Registros con id_propiedad vacío después: {vacios_despues}")
        
        # Mostrar ejemplos
        print("\n   Ejemplos de registros actualizados:")
        cursor.execute("SELECT TOP 3 id, identificador_externo, id_propiedad FROM ingestas_propiedadraw WHERE id_propiedad IS NOT NULL AND id_propiedad != '' ORDER BY id DESC")
        for row in cursor.fetchall():
            print(f"      ID: {row[0]}, Identificador: '{row[1]}', ID Propiedad: '{row[2]}'")
    
    print("\n" + "=" * 60)
    print("✓ CORRECCIÓN COMPLETADA EXITOSAMENTE")
    print("\nEl campo id_propiedad (id_de_la_propiedad en la tabla)")
    print("ahora contiene los valores de identificador_externo.")
    
except ImportError as e:
    print(f"Error de importación: {e}")
    print("\nAsegúrate de que:")
    print("1. Estás en el directorio correcto (webapp)")
    print("2. Django está instalado")
    print("3. La configuración de webapp.settings existe")
    
except Exception as e:
    print(f"Error durante la ejecución: {e}")
    import traceback
    traceback.print_exc()