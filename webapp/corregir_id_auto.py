"""
Script AUTOMÁTICO para corregir el campo id_propiedad.
Ejecuta la corrección sin pedir confirmación.
"""

import pyodbc
import os

def conectar_bd():
    """Conectar a la base de datos SQL Server."""
    try:
        # Parámetros de conexión
        server = 'localhost'
        database = 'prometeo'
        trusted_connection = 'yes'
        
        connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection={trusted_connection}'
        conn = pyodbc.connect(connection_string)
        return conn
    except Exception as e:
        print(f"Error al conectar: {e}")
        # Intentar conexión alternativa
        try:
            conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=(local);DATABASE=prometeo;Trusted_Connection=yes')
            return conn
        except Exception as e2:
            print(f"Error en conexión alternativa: {e2}")
            return None

def ejecutar_correccion():
    """Ejecutar la corrección automáticamente."""
    print("CORRECCIÓN AUTOMÁTICA DE id_propiedad")
    print("=" * 50)
    
    # Conectar a la base de datos
    conn = conectar_bd()
    if not conn:
        print("✗ No se pudo conectar a la base de datos.")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 1. Verificar cuántos registros se pueden corregir
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ingestas_propiedadraw 
            WHERE (id_propiedad IS NULL OR id_propiedad = '')
            AND (identificador_externo IS NOT NULL AND identificador_externo != '')
        """)
        corregibles = cursor.fetchone()[0]
        
        print(f"Registros que se pueden corregir: {corregibles}")
        
        if corregibles == 0:
            print("No hay registros para corregir.")
            print("\nPosibles causas:")
            
            # Verificar estado de los campos
            cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
            total = cursor.fetchone()[0]
            print(f"1. Total de registros: {total}")
            
            cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE identificador_externo IS NULL OR identificador_externo = ''")
            sin_identificador = cursor.fetchone()[0]
            print(f"2. Registros sin identificador_externo: {sin_identificador}")
            
            cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE id_propiedad IS NOT NULL AND id_propiedad != ''")
            con_id_propiedad = cursor.fetchone()[0]
            print(f"3. Registros con id_propiedad ya lleno: {con_id_propiedad}")
            
            return True
        
        # 2. Ejecutar la corrección
        print(f"\nEjecutando corrección de {corregibles} registros...")
        
        cursor.execute("""
            UPDATE ingestas_propiedadraw 
            SET id_propiedad = identificador_externo
            WHERE (id_propiedad IS NULL OR id_propiedad = '')
            AND (identificador_externo IS NOT NULL AND identificador_externo != '')
        """)
        
        filas_afectadas = cursor.rowcount
        conn.commit()
        
        print(f"✓ {filas_afectadas} registros actualizados.")
        
        # 3. Verificar resultado
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE (id_propiedad IS NULL OR id_propiedad = '')")
        vacios_despues = cursor.fetchone()[0]
        print(f"✓ Registros con id_propiedad vacío después: {vacios_despues}")
        
        # 4. Mostrar algunos ejemplos actualizados
        print("\nEjemplos de registros actualizados (primeros 3):")
        cursor.execute("""
            SELECT TOP 3 
                id, 
                identificador_externo,
                id_propiedad
            FROM ingestas_propiedadraw 
            WHERE id_propiedad IS NOT NULL AND id_propiedad != ''
            ORDER BY id DESC
        """)
        for r in cursor.fetchall():
            print(f"   ID: {r[0]}, Identificador: '{r[1]}', ID Propiedad: '{r[2]}'")
        
        return True
        
    except Exception as e:
        print(f"✗ Error durante la corrección: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        conn.close()
        print("\nConexión cerrada.")

if __name__ == "__main__":
    print("Iniciando corrección automática...")
    if ejecutar_correccion():
        print("\n" + "=" * 50)
        print("PROCESO COMPLETADO")
        print("\nEl campo id_propiedad ha sido actualizado con los valores")
        print("de identificador_externo donde estaba vacío.")
    else:
        print("\n" + "=" * 50)
        print("PROCESO FALLÓ")
        print("\nNo se pudo completar la corrección.")