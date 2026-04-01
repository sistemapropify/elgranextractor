"""
Diagnóstico del problema con el campo id e identificador_externo en propiedadraw.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db import connection

def analizar_estructura():
    """Analizar la estructura de la tabla propiedadraw."""
    print("=== ANÁLISIS DE ESTRUCTURA DE TABLA propiedadraw ===")
    
    # Obtener campos del modelo
    campos = PropiedadRaw._meta.get_fields()
    print("\n1. Campos del modelo PropiedadRaw:")
    for campo in campos:
        tipo = campo.get_internal_type()
        print(f"   - {campo.name} ({tipo})")
    
    # Campos clave
    print("\n2. Campos clave identificadores:")
    print(f"   - id: Primary Key auto-incremental")
    print(f"   - identificador_externo: ID de la propiedad en la fuente original")
    print(f"   - id_propiedad: Otro identificador de propiedad")
    
    # Verificar datos en la base de datos
    print("\n3. Verificación de datos en la tabla:")
    with connection.cursor() as cursor:
        # Contar registros
        cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw")
        total = cursor.fetchone()[0]
        print(f"   Total de registros: {total}")
        
        # Verificar valores nulos en identificador_externo
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN identificador_externo IS NULL OR identificador_externo = '' THEN 1 ELSE 0 END) as nulos,
                SUM(CASE WHEN identificador_externo IS NOT NULL AND identificador_externo != '' THEN 1 ELSE 0 END) as con_valor
            FROM ingestas_propiedadraw
        """)
        row = cursor.fetchone()
        print(f"   Registros con identificador_externo: {row[2]}")
        print(f"   Registros sin identificador_externo: {row[1]}")
        
        # Verificar valores nulos en id_propiedad
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN id_propiedad IS NULL OR id_propiedad = '' THEN 1 ELSE 0 END) as nulos,
                SUM(CASE WHEN id_propiedad IS NOT NULL AND id_propiedad != '' THEN 1 ELSE 0 END) as con_valor
            FROM ingestas_propiedadraw
        """)
        row = cursor.fetchone()
        print(f"   Registros con id_propiedad: {row[2]}")
        print(f"   Registros sin id_propiedad: {row[1]}")
        
        # Mostrar algunos ejemplos
        if total > 0:
            print("\n4. Ejemplos de registros (primeros 5):")
            cursor.execute("""
                SELECT TOP 5 
                    id, 
                    identificador_externo,
                    id_propiedad,
                    tipo_propiedad,
                    precio_usd
                FROM ingestas_propiedadraw 
                ORDER BY id
            """)
            for row in cursor.fetchall():
                print(f"   ID: {row[0]}, Identificador Externo: {row[1]}, ID Propiedad: {row[2]}, Tipo: {row[3]}, Precio: {row[4]}")

def analizar_problema():
    """Analizar el problema específico mencionado por el usuario."""
    print("\n=== DIAGNÓSTICO DEL PROBLEMA ===")
    print("\nProblema identificado:")
    print("1. El campo 'id' es generado automáticamente por la base de datos (auto-incremental)")
    print("2. El campo 'identificador_externo' debería contener el ID original del Excel")
    print("3. El campo 'id_propiedad' también podría ser un identificador")
    print("\nPosibles causas:")
    print("   - El Excel no tiene columna 'identificador-externo' o tiene otro nombre")
    print("   - El mapeo en importar_excel_propiedadraw.py no está capturando este campo")
    print("   - Los datos se importaron antes de que existiera el campo identificador_externo")
    print("   - El campo importante en Excel se llama diferente (ej: 'ID', 'Código', 'Referencia')")

def verificar_mapeo_excel():
    """Verificar el mapeo actual del Excel."""
    print("\n=== VERIFICACIÓN DE MAPEO EXCEL ===")
    
    # Mapeo actual del archivo importar_excel_propiedadraw.py
    mapeo_actual = {
        'identificador-externo': 'identificador_externo',
        'ID de la Propiedad': 'id_propiedad',
        'fuente-excel': 'fuente_excel'
    }
    
    print("Mapeo actual en importar_excel_propiedadraw.py:")
    for col_excel, campo_bd in mapeo_actual.items():
        print(f"   '{col_excel}' -> '{campo_bd}'")
    
    print("\nRecomendaciones:")
    print("1. Verificar que el Excel tenga columna 'identificador-externo'")
    print("2. Si no existe, buscar columna con el ID original (ej: 'ID', 'Código')")
    print("3. Actualizar el mapeo en importar_excel_propiedadraw.py si es necesario")

def proponer_solucion():
    """Proponer solución al problema."""
    print("\n=== SOLUCIÓN PROPUESTA ===")
    
    print("\nOPCIÓN 1: Actualizar mapeo de importación")
    print("   1. Verificar el nombre exacto de la columna en el Excel")
    print("   2. Agregar mapeo en importar_excel_propiedadraw.py:")
    print("      Ejemplo: 'ID Original' -> 'identificador_externo'")
    print("   3. Reimportar los datos")
    
    print("\nOPCIÓN 2: Actualizar datos existentes")
    print("   1. Si id_propiedad contiene el identificador correcto:")
    print("      UPDATE ingestas_propiedadraw SET identificador_externo = id_propiedad")
    print("      WHERE identificador_externo IS NULL")
    
    print("\nOPCIÓN 3: Crear script de migración")
    print("   1. Leer el Excel original para obtener los IDs")
    print("   2. Actualizar identificador_externo basado en coincidencias")
    
    print("\nAcciones inmediatas recomendadas:")
    print("   1. Ejecutar: python webapp/check_mapping2.py para ver columnas del Excel")
    print("   2. Revisar el archivo Excel para ver el nombre de la columna de ID")
    print("   3. Actualizar el mapeo en importar_excel_propiedadraw.py")
    print("   4. Reimportar o actualizar los datos")

if __name__ == "__main__":
    try:
        analizar_estructura()
        analizar_problema()
        verificar_mapeo_excel()
        proponer_solucion()
    except Exception as e:
        print(f"Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc()