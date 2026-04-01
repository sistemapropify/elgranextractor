"""
Script simple para testear la conexión a la base de datos.
"""

import os
import sys

print("Test de conexión a la base de datos")
print("=" * 50)

# Intentar diferentes configuraciones
try:
    # Opción 1: Usar django.db directamente
    print("\n1. Intentando conectar usando Django...")
    
    # Configurar path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    # Configurar settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
    
    import django
    django.setup()
    
    from django.db import connection
    
    print("   ✓ Django configurado correctamente")
    
    # Testear conexión
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"   ✓ Conexión a BD exitosa: {result[0]}")
        
        # Verificar tabla
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'ingestas_propiedadraw'")
        tabla_existe = cursor.fetchone()[0]
        
        if tabla_existe:
            print("   ✓ Tabla 'ingestas_propiedadraw' existe")
            
            # Verificar datos
            cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
            total = cursor.fetchone()[0]
            print(f"   ✓ Total de registros: {total}")
            
            # Verificar campos
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'ingestas_propiedadraw' 
                AND COLUMN_NAME IN ('id_propiedad', 'identificador_externo')
            """)
            campos = [row[0] for row in cursor.fetchall()]
            print(f"   ✓ Campos encontrados: {campos}")
            
            # Verificar estado actual
            cursor.execute("SELECT TOP 3 id, identificador_externo, id_propiedad FROM ingestas_propiedadraw ORDER BY id")
            print("\n   Primeros 3 registros:")
            for row in cursor.fetchall():
                print(f"      ID: {row[0]}, Identificador: '{row[1]}', ID Propiedad: '{row[2]}'")
                
        else:
            print("   ✗ Tabla 'ingestas_propiedadraw' no existe")
            
except Exception as e:
    print(f"   ✗ Error: {e}")
    
    # Opción 2: Intentar con pyodbc directamente
    print("\n2. Intentando conectar directamente con pyodbc...")
    try:
        import pyodbc
        
        # Intentar diferentes cadenas de conexión
        connection_strings = [
            'DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=prometeo;Trusted_Connection=yes',
            'DRIVER={SQL Server};SERVER=localhost;DATABASE=prometeo;Trusted_Connection=yes',
            'DRIVER={SQL Server Native Client 11.0};SERVER=localhost;DATABASE=prometeo;Trusted_Connection=yes',
        ]
        
        for conn_str in connection_strings:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                print(f"   ✓ Conexión exitosa con: {conn_str[:50]}...")
                conn.close()
                break
            except Exception as e2:
                print(f"   ✗ Falló: {e2}")
                
    except ImportError:
        print("   ✗ pyodbc no está instalado")
        
print("\n" + "=" * 50)
print("Test completado")