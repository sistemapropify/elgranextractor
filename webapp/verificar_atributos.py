import os
import sys
import django
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw, CampoDinamico

print("=== Verificación de atributos_extras ===")
total = PropiedadRaw.objects.count()
print(f"Total propiedades: {total}")

# Contar propiedades con atributos_extras no vacíos
con_atributos = PropiedadRaw.objects.exclude(atributos_extras={}).count()
print(f"Propiedades con atributos_extras no vacíos: {con_atributos}")

if con_atributos > 0:
    p = PropiedadRaw.objects.exclude(atributos_extras={}).first()
    print(f"\nEjemplo de atributos_extras (ID {p.id}):")
    print(json.dumps(p.atributos_extras, indent=2, ensure_ascii=False))
    
    # Ver keys
    keys = list(p.atributos_extras.keys())
    print(f"\nKeys en este registro: {keys}")
    
    # Comparar con campos dinámicos
    campos = CampoDinamico.objects.all()
    print(f"\nCampos dinámicos existentes ({campos.count()}):")
    for cd in campos:
        print(f"  - {cd.nombre_campo_bd} ({cd.tipo_dato})")
    
    # Ver si alguna key coincide
    for key in keys:
        coinciden = [cd for cd in campos if cd.nombre_campo_bd.lower() == key.lower()]
        if coinciden:
            print(f"Key '{key}' coincide con campo dinámico: {coinciden[0].nombre_campo_bd}")
        else:
            print(f"Key '{key}' NO tiene campo dinámico correspondiente")
else:
    print("\nNo hay atributos_extras. Puede que ya se migraron.")
    # Verificar si hay datos en campos dinámicos (muestra)
    campos = CampoDinamico.objects.all()
    print(f"Campos dinámicos: {campos.count()}")
    for cd in campos[:5]:
        # Contar propiedades con valor no nulo en esa columna (necesitaríamos SQL)
        print(f"  - {cd.nombre_campo_bd}")

# Verificar si las columnas físicas existen
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ingestas_propiedadraw'")
    columnas = [row[0] for row in cursor.fetchall()]
print(f"\nColumnas físicas en tabla: {len(columnas)}")
# Buscar columnas dinámicas (que no sean campos fijos)
campos_fijos = ['id', 'fuente_excel', 'fecha_ingesta', 'tipo_propiedad', 'precio_usd', 'moneda', 'ubicacion', 'metros_cuadrados', 'habitaciones', 'banos', 'estacionamientos', 'descripcion', 'url_fuente', 'atributos_extras']
columnas_dinamicas = [c for c in columnas if c not in campos_fijos]
print(f"Columnas dinámicas (posibles): {columnas_dinamicas}")