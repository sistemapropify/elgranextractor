import os
import django
import sys

# Configurar Django - ajustar el path para que encuentre el módulo webapp
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connection

def check_constraints():
    """Verificar las restricciones CHECK en la tabla ingestas_propiedadraw"""
    with connection.cursor() as cursor:
        # Consulta para obtener las restricciones CHECK
        query = """
        SELECT 
            cc.name as constraint_name,
            cc.definition,
            col.name as column_name
        FROM sys.check_constraints cc
        INNER JOIN sys.objects o ON cc.parent_object_id = o.object_id
        INNER JOIN sys.columns col ON cc.parent_column_id = col.column_id AND cc.parent_object_id = col.object_id
        WHERE o.name = 'ingestas_propiedadraw'
        """
        cursor.execute(query)
        constraints = cursor.fetchall()
        
        print("Restricciones CHECK en la tabla ingestas_propiedadraw:")
        print("=" * 80)
        for constraint_name, definition, column_name in constraints:
            print(f"Nombre: {constraint_name}")
            print(f"Columna: {column_name}")
            print(f"Definición: {definition}")
            print("-" * 80)
        
        # También verificar el tipo de datos de la columna atributos_extras
        query_type = """
        SELECT 
            c.name as column_name,
            t.name as data_type,
            c.max_length,
            c.is_nullable
        FROM sys.columns c
        INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
        WHERE c.object_id = OBJECT_ID('ingestas_propiedadraw')
        AND c.name = 'atributos_extras'
        """
        cursor.execute(query_type)
        column_info = cursor.fetchall()
        
        print("\nInformación de la columna atributos_extras:")
        print("=" * 80)
        for col_name, data_type, max_length, is_nullable in column_info:
            print(f"Columna: {col_name}")
            print(f"Tipo de datos: {data_type}")
            print(f"Longitud máxima: {max_length}")
            print(f"Puede ser nulo: {'Sí' if is_nullable else 'No'}")

if __name__ == "__main__":
    check_constraints()