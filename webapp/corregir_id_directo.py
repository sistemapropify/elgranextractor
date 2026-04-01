"""
Script DIRECTO para corregir el campo id_propiedad con identificador_externo.
Ejecuta SQL directamente sin depender de Django.
"""

import pyodbc
import os

def conectar_bd():
    """Conectar a la base de datos SQL Server."""
    try:
        # Parámetros de conexión (ajustar según tu configuración)
        server = 'localhost'
        database = 'prometeo'
        trusted_connection = 'yes'  # Usar autenticación de Windows
        
        connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection={trusted_connection}'
        conn = pyodbc.connect(connection_string)
        return conn
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        print("\nIntentando con conexión alternativa...")
        
        # Intentar conexión alternativa
        try:
            conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=prometeo;Trusted_Connection=yes')
            return conn
        except Exception as e2:
            print(f"Error en conexión alternativa: {e2}")
            return None

def verificar_estado(conn):
    """Verificar el estado actual de los datos."""
    cursor = conn.cursor()
    
    print("=== VERIFICACIÓN DE ESTADO ACTUAL ===")
    
    # 1. Contar registros totales
    cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
    total = cursor.fetchone()[0]
    print(f"1. Total de registros en la tabla: {total}")
    
    # 2. Verificar id_propiedad
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN id_propiedad IS NULL OR id_propiedad = '' THEN 1 ELSE 0 END) as vacios,
            SUM(CASE WHEN id_propiedad IS NOT NULL AND id_propiedad != '' THEN 1 ELSE 0 END) as con_valor
        FROM ingestas_propiedadraw
    """)
    row = cursor.fetchone()
    print(f"2. Campo id_propiedad:")
    print(f"   - Con valor: {row[2]}")
    print(f"   - Vacíos: {row[1]}")
    
    # 3. Verificar identificador_externo
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN identificador_externo IS NULL OR identificador_externo = '' THEN 1 ELSE 0 END) as vacios,
            SUM(CASE WHEN identificador_externo IS NOT NULL AND identificador_externo != '' THEN 1 ELSE 0 END) as con_valor
        FROM ingestas_propiedadraw
    """)
    row = cursor.fetchone()
    print(f"3. Campo identificador_externo:")
    print(f"   - Con valor: {row[2]}")
    print(f"   - Vacíos: {row[1]}")
    
    # 4. Verificar cuántos se pueden corregir
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ingestas_propiedadraw 
        WHERE (id_propiedad IS NULL OR id_propiedad = '')
        AND (identificador_externo IS NOT NULL AND identificador_externo != '')
    """)
    corregibles = cursor.fetchone()[0]
    print(f"4. Registros que se pueden corregir: {corregibles}")
    
    # 5. Mostrar ejemplos
    if corregibles > 0:
        print("\5. Ejemplos de registros a corregir (primeros 5):")
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
            print(f"   ID: {r[0]}, Identificador Externo: '{r[1]}', ID Propiedad: '{r[2]}'")
    
    return corregibles

def corregir_datos(conn):
    """Corregir los datos actualizando id_propiedad."""
    cursor = conn.cursor()
    
    print("\n=== EJECUTANDO CORRECCIÓN ===")
    
    try:
        # Ejecutar la actualización
        cursor.execute("""
            UPDATE ingestas_propiedadraw 
            SET id_propiedad = identificador_externo
            WHERE (id_propiedad IS NULL OR id_propiedad = '')
            AND (identificador_externo IS NOT NULL AND identificador_externo != '')
        """)
        
        filas_afectadas = cursor.rowcount
        conn.commit()
        
        print(f"✓ {filas_afectadas} registros actualizados correctamente.")
        
        # Verificar resultado
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ingestas_propiedadraw 
            WHERE (id_propiedad IS NULL OR id_propiedad = '')
        """)
        vacios_despues = cursor.fetchone()[0]
        print(f"✓ Registros con id_propiedad vacío después: {vacios_despues}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error al ejecutar la corrección: {e}")
        conn.rollback()
        return False

def main():
    """Función principal."""
    print("CORRECCIÓN DE CAMPO id_propiedad EN TABLA propiedadraw")
    print("=" * 60)
    
    # Conectar a la base de datos
    conn = conectar_bd()
    if not conn:
        print("No se pudo conectar a la base de datos.")
        print("Asegúrate de que:")
        print("1. SQL Server esté ejecutándose")
        print("2. La base de datos 'prometeo' exista")
        print("3. pyodbc esté instalado (pip install pyodbc)")
        return
    
    try:
        # Verificar estado
        corregibles = verificar_estado(conn)
        
        if corregibles == 0:
            print("\nNo hay registros para corregir.")
            print("Posibles razones:")
            print("1. identificador_externo también está vacío")
            print("2. id_propiedad ya tiene valores")
            print("3. La tabla está vacía")
            return
        
        # Preguntar confirmación
        print(f"\n¿Desea corregir {corregibles} registros?")
        respuesta = input("Escriba 'SI' para continuar: ").strip().upper()
        
        if respuesta == 'SI':
            # Ejecutar corrección
            if corregir_datos(conn):
                print("\n✓ Corrección completada exitosamente.")
                print("\nRecomendaciones:")
                print("1. Verificar en la aplicación que los datos se muestren correctamente")
                print("2. Para futuras importaciones, asegurarse de que el mapeo en")
                print("   importar_excel_propiedadraw.py esté configurado correctamente")
            else:
                print("\n✗ La corrección falló.")
        else:
            print("\n✗ Operación cancelada por el usuario.")
            
    finally:
        conn.close()
        print("\nConexión a la base de datos cerrada.")

if __name__ == "__main__":
    main()