import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connections

def explore_lead_statuses():
    """Explorar estructura de tabla crm_lead_statuses"""
    try:
        with connections['propifai'].cursor() as cursor:
            # Verificar si existe la tabla
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'crm_lead_statuses'
            """)
            tables = cursor.fetchall()
            if not tables:
                print("Tabla crm_lead_statuses no encontrada")
                return
            
            # Obtener estructura
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'crm_lead_statuses'
                ORDER BY ORDINAL_POSITION
            """)
            print("Estructura de crm_lead_statuses:")
            for col in cursor.fetchall():
                print(f"  {col[0]} ({col[1]}) - Nullable: {col[2]}")
            
            # Obtener algunos registros
            cursor.execute("""
                SELECT TOP 10 id, name, is_active
                FROM crm_lead_statuses
                ORDER BY id
            """)
            print("\nEjemplos de estados:")
            for row in cursor.fetchall():
                print(f"  ID: {row[0]}, Nombre: {row[1]}, Activo: {row[2]}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    explore_lead_statuses()