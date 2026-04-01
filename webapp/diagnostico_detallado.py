"""
Diagnóstico detallado del problema con id_propiedad.
"""

print("DIAGNÓSTICO DETALLADO - CAMPO id_propiedad VACÍO")
print("=" * 60)

print("\n1. POSIBLES CAUSAS DEL PROBLEMA:")
print("   a) La tabla está vacía (no hay datos)")
print("   b) identificador_externo también está vacío")
print("   c) El nombre del campo en la BD es diferente")
print("   d) Ya se ejecutó la corrección pero hay otro problema")
print("   e) Los datos no se importaron correctamente")

print("\n2. VERIFICACIÓN PASO A PASO:")

# Intentar conectar de forma simple
try:
    import pyodbc
    
    print("\n   Intentando conectar a la base de datos...")
    
    # Probar diferentes cadenas de conexión
    connection_strings = [
        'DRIVER={ODBC Driver 17 for SQL Server};SERVER=(local);DATABASE=prometeo;Trusted_Connection=yes',
        'DRIVER={SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=prometeo;Trusted_Connection=yes',
        'DRIVER={SQL Server};SERVER=localhost;DATABASE=prometeo;Trusted_Connection=yes',
    ]
    
    conn = None
    for conn_str in connection_strings:
        try:
            print(f"   Probando: {conn_str[:60]}...")
            conn = pyodbc.connect(conn_str)
            print("   ✓ Conexión exitosa")
            break
        except Exception as e:
            print(f"   ✗ Error: {str(e)[:50]}...")
            continue
    
    if not conn:
        print("\n   ✗ No se pudo conectar a ninguna base de datos.")
        print("\n   SOLUCIÓN: Verificar que SQL Server esté ejecutándose.")
        exit(1)
    
    cursor = conn.cursor()
    
    # Verificar si la tabla existe
    print("\n   Verificando tabla 'ingestas_propiedadraw'...")
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
    """)
    
    if cursor.fetchone():
        print("   ✓ Tabla existe")
    else:
        print("   ✗ Tabla NO existe")
        print("\n   SOLUCIÓN: La tabla no existe. Verificar migraciones de Django.")
        conn.close()
        exit(1)
    
    # Verificar estructura de la tabla
    print("\n   Verificando estructura de la tabla...")
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
        ORDER BY ORDINAL_POSITION
    """)
    
    columnas = cursor.fetchall()
    print(f"   Total de columnas: {len(columnas)}")
    
    # Buscar columnas específicas
    columnas_buscadas = ['id_propiedad', 'identificador_externo', 'id_de_la_propiedad']
    encontradas = []
    
    for col in columnas:
        nombre = col[0]
        tipo = col[1]
        nullable = col[2]
        
        if nombre.lower() in [c.lower() for c in columnas_buscadas]:
            print(f"   ✓ {nombre} ({tipo}, nullable: {nullable})")
            encontradas.append(nombre)
    
    # Verificar nombres exactos
    print("\n   Nombres exactos de columnas relacionadas con ID:")
    cursor.execute("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
        AND COLUMN_NAME LIKE '%id%' 
        OR COLUMN_NAME LIKE '%identif%'
        ORDER BY COLUMN_NAME
    """)
    
    for row in cursor.fetchall():
        print(f"   - {row[0]}")
    
    # Verificar datos
    print("\n   Verificando datos en la tabla...")
    cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
    total = cursor.fetchone()[0]
    print(f"   Total de registros: {total}")
    
    if total == 0:
        print("\n   ✗ La tabla está VACÍA.")
        print("\n   SOLUCIÓN: Importar datos desde Excel.")
        conn.close()
        exit(1)
    
    # Verificar estado de los campos
    print("\n   Estado actual de los campos:")
    
    # Primero necesitamos saber el nombre exacto del campo
    cursor.execute("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
        AND (COLUMN_NAME LIKE '%id_propiedad%' OR COLUMN_NAME = 'id_de_la_propiedad')
    """)
    
    campo_id_propiedad = None
    for row in cursor.fetchall():
        campo_id_propiedad = row[0]
        break
    
    if not campo_id_propiedad:
        print("   ✗ No se encontró campo id_propiedad o id_de_la_propiedad")
        # Buscar cualquier campo que pueda ser
        cursor.execute("SELECT TOP 1 * FROM ingestas_propiedadraw")
        desc = cursor.description
        print("\n   Campos disponibles (primer registro):")
        for i, col in enumerate(desc):
            print(f"   {i+1}. {col[0]}")
        conn.close()
        exit(1)
    
    print(f"   Campo encontrado: {campo_id_propiedad}")
    
    # Verificar valores
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN {campo_id_propiedad} IS NULL OR {campo_id_propiedad} = '' THEN 1 ELSE 0 END) as vacios,
            SUM(CASE WHEN {campo_id_propiedad} IS NOT NULL AND {campo_id_propiedad} != '' THEN 1 ELSE 0 END) as con_valor
        FROM ingestas_propiedadraw
    """)
    
    stats = cursor.fetchone()
    print(f"   - Con valor: {stats[2]}")
    print(f"   - Vacíos: {stats[1]}")
    
    # Verificar identificador_externo
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN identificador_externo IS NULL OR identificador_externo = '' THEN 1 ELSE 0 END) as vacios,
            SUM(CASE WHEN identificador_externo IS NOT NULL AND identificador_externo != '' THEN 1 ELSE 0 END) as con_valor
        FROM ingestas_propiedadraw
    """)
    
    stats_id = cursor.fetchone()
    print(f"   identificador_externo - Con valor: {stats_id[2]}, Vacíos: {stats_id[1]}")
    
    # Mostrar ejemplos
    print("\n   Ejemplos de registros (primeros 3):")
    cursor.execute(f"SELECT TOP 3 id, identificador_externo, {campo_id_propiedad} FROM ingestas_propiedadraw ORDER BY id")
    
    for row in cursor.fetchall():
        print(f"   ID: {row[0]}, Identificador: '{row[1]}', {campo_id_propiedad}: '{row[2]}'")
    
    # Verificar si se puede corregir
    if stats[1] > 0 and stats_id[2] > 0:
        print(f"\n   ✓ SE PUEDE CORREGIR: {stats[1]} registros con {campo_id_propiedad} vacío y identificador_externo con valor")
        
        # Ejecutar corrección
        print("\n   Ejecutando corrección...")
        cursor.execute(f"""
            UPDATE ingestas_propiedadraw 
            SET {campo_id_propiedad} = identificador_externo
            WHERE ({campo_id_propiedad} IS NULL OR {campo_id_propiedad} = '')
            AND (identificador_externo IS NOT NULL AND identificador_externo != '')
        """)
        
        actualizados = cursor.rowcount
        conn.commit()
        print(f"   ✓ {actualizados} registros actualizados.")
        
        # Verificar después
        cursor.execute(f"SELECT COUNT(*) FROM ingestas_propiedadraw WHERE {campo_id_propiedad} IS NULL OR {campo_id_propiedad} = ''")
        vacios_despues = cursor.fetchone()[0]
        print(f"   Registros vacíos después: {vacios_despues}")
        
    else:
        print("\n   ✗ NO SE PUEDE CORREGIR:")
        if stats[1] == 0:
            print("   - id_propiedad ya tiene valores")
        if stats_id[2] == 0:
            print("   - identificador_externo también está vacío")
    
    conn.close()
    
except ImportError:
    print("\n   ✗ pyodbc no está instalado.")
    print("\n   SOLUCIÓN: Ejecutar 'pip install pyodbc'")
    
except Exception as e:
    print(f"\n   ✗ Error general: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("\nSi el problema persiste, verificar:")
print("1. Que la base de datos 'prometeo' existe")
print("2. Que la tabla 'ingestas_propiedadraw' tiene datos")
print("3. Que los campos tienen los nombres correctos")
print("4. Ejecutar manualmente el SQL de corrección")