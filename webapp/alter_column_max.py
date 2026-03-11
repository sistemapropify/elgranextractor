import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from django.db import connection

sql_statements = [
    "ALTER TABLE ingestas_propiedadraw ALTER COLUMN imagenes_de_la_propiedad varchar(max)",
    "ALTER TABLE ingestas_propiedadraw ALTER COLUMN url_de_la_propiedad varchar(max)",
    "ALTER TABLE ingestas_propiedadraw ALTER COLUMN descripcion_detallada varchar(max)",
    "ALTER TABLE ingestas_propiedadraw ALTER COLUMN agente_inmobiliario varchar(max)",
]

with connection.cursor() as cursor:
    for sql in sql_statements:
        try:
            cursor.execute(sql)
            print(f"Ejecutado: {sql}")
        except Exception as e:
            print(f"Error al ejecutar {sql}: {e}")