import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connections
from django.db.utils import OperationalError

def explore_tables():
    """Explorar estructura de tablas relacionadas con asignación de leads"""
    try:
        # Usar la conexión 'propifai'
        with connections['propifai'].cursor() as cursor:
            # Verificar si existe la tabla crm_leads_assigned_to
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME IN ('crm_leads_assigned_to', 'users')
            """)
            tables = cursor.fetchall()
            print("Tablas encontradas:")
            for table in tables:
                print(f"  - {table[0]}")
            
            # Obtener estructura de crm_leads_assigned_to
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'crm_leads_assigned_to'
                ORDER BY ORDINAL_POSITION
            """)
            print("\nEstructura de crm_leads_assigned_to:")
            for col in cursor.fetchall():
                print(f"  {col[0]} ({col[1]}) - Nullable: {col[2]}")
            
            # Obtener estructura de users
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'users'
                ORDER BY ORDINAL_POSITION
            """)
            print("\nEstructura de users:")
            for col in cursor.fetchall():
                print(f"  {col[0]} ({col[1]}) - Nullable: {col[2]}")
            
            # Verificar algunas filas de ejemplo
            cursor.execute("""
                SELECT TOP 5 lead_id, customuser_id
                FROM crm_leads_assigned_to
            """)
            print("\nEjemplos de asignaciones:")
            for row in cursor.fetchall():
                print(f"  Lead ID: {row[0]}, CustomUser ID: {row[1]}")
                
            # Verificar usuarios correspondientes
            cursor.execute("""
                SELECT TOP 5 id, first_name, last_name, username
                FROM users
                ORDER BY id
            """)
            print("\nEjemplos de usuarios:")
            for row in cursor.fetchall():
                print(f"  ID: {row[0]}, Nombre: {row[1]} {row[2]}, Username: {row[3]}")
                
    except OperationalError as e:
        print(f"Error de conexión: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    explore_tables()