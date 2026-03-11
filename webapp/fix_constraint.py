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

def fix_constraint():
    """Modificar la restricción CHECK para permitir cadenas vacías o NULL"""
    with connection.cursor() as cursor:
        # Primero, verificar si la restricción existe
        check_query = """
        SELECT name FROM sys.check_constraints 
        WHERE parent_object_id = OBJECT_ID('ingestas_propiedadraw')
        AND name = 'ingestas_propiedadraw_atributos_extras_2161c86e_check'
        """
        cursor.execute(check_query)
        constraint = cursor.fetchone()
        
        if constraint:
            constraint_name = constraint[0]
            print(f"Encontrada restricción: {constraint_name}")
            
            # Eliminar la restricción CHECK existente
            drop_query = f"""
            ALTER TABLE ingestas_propiedadraw
            DROP CONSTRAINT {constraint_name}
            """
            try:
                cursor.execute(drop_query)
                print(f"Restricción {constraint_name} eliminada exitosamente")
            except Exception as e:
                print(f"Error al eliminar restricción: {e}")
                
            # Crear una nueva restricción CHECK más permisiva
            # Que permita NULL, cadena vacía, o JSON válido
            new_check_query = """
            ALTER TABLE ingestas_propiedadraw
            ADD CONSTRAINT CK_atributos_extras_valid_json 
            CHECK (atributos_extras IS NULL OR 
                   atributos_extras = '' OR 
                   ISJSON(atributos_extras) = 1)
            """
            try:
                cursor.execute(new_check_query)
                print("Nueva restricción CHECK creada exitosamente")
            except Exception as e:
                print(f"Error al crear nueva restricción: {e}")
        else:
            print("No se encontró la restricción CHECK")
        
        # También podemos intentar hacer que la columna acepte NULL
        # Primero necesitamos eliminar cualquier restricción DEFAULT que impida NULL
        alter_query = """
        ALTER TABLE ingestas_propiedadraw
        ALTER COLUMN atributos_extras nvarchar(MAX) NULL
        """
        try:
            cursor.execute(alter_query)
            print("Columna atributos_extras modificada para aceptar NULL")
        except Exception as e:
            print(f"Error al modificar columna: {e}")

if __name__ == "__main__":
    fix_constraint()