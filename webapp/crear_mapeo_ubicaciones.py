#!/usr/bin/env python
"""
Script para crear mapeo de índices a nombres para ubicaciones en Propifai.
"""
import os
import sys
import json
import django
from django.db import connections

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def crear_mapeo_completo():
    print("CREANDO MAPEO DE UBICACIONES PARA PROPIFAI")
    print("=" * 70)
    
    # Conectar a la base de datos propifai
    connection = connections['propifai']
    
    try:
        with connection.cursor() as cursor:
            # 1. Mapeo de departamentos (properties_department)
            print("\n1. MAPEO DE DEPARTAMENTOS:")
            print("-" * 50)
            cursor.execute("SELECT id, name FROM properties_department ORDER BY id")
            departamentos = cursor.fetchall()
            mapeo_departamentos = {str(row[0]): row[1] for row in departamentos}
            print(f"Departamentos mapeados: {len(mapeo_departamentos)}")
            
            # Mostrar algunos ejemplos
            for i, (id_str, nombre) in enumerate(list(mapeo_departamentos.items())[:5]):
                print(f"  ID {id_str}: {nombre}")
            if len(mapeo_departamentos) > 5:
                print(f"  ... y {len(mapeo_departamentos) - 5} más")
            
            # 2. Mapeo de provincias (properties_province)
            print("\n2. MAPEO DE PROVINCIAS:")
            print("-" * 50)
            cursor.execute("SELECT id, name FROM properties_province ORDER BY id")
            provincias = cursor.fetchall()
            mapeo_provincias = {str(row[0]): row[1] for row in provincias}
            print(f"Provincias mapeadas: {len(mapeo_provincias)}")
            
            # Mostrar algunos ejemplos
            for i, (id_str, nombre) in enumerate(list(mapeo_provincias.items())[:5]):
                print(f"  ID {id_str}: {nombre}")
            if len(mapeo_provincias) > 5:
                print(f"  ... y {len(mapeo_provincias) - 5} más")
            
            # 3. Mapeo de distritos (properties_district)
            print("\n3. MAPEO DE DISTRITOS:")
            print("-" * 50)
            cursor.execute("SELECT id, name FROM properties_district ORDER BY id")
            distritos = cursor.fetchall()
            mapeo_distritos = {str(row[0]): row[1] for row in distritos}
            print(f"Distritos mapeados: {len(mapeo_distritos)}")
            
            # Mostrar algunos ejemplos
            for i, (id_str, nombre) in enumerate(list(mapeo_distritos.items())[:10]):
                print(f"  ID {id_str}: {nombre}")
            if len(mapeo_distritos) > 10:
                print(f"  ... y {len(mapeo_distritos) - 10} más")
            
            # 4. Verificar valores únicos en properties
            print("\n4. VALORES ÚNICOS EN PROPERTIES:")
            print("-" * 50)
            
            # Obtener valores únicos de department, province, district
            cursor.execute("SELECT DISTINCT department FROM properties WHERE department IS NOT NULL")
            dept_unicos = [str(row[0]) for row in cursor.fetchall()]
            
            cursor.execute("SELECT DISTINCT province FROM properties WHERE province IS NOT NULL")
            prov_unicos = [str(row[0]) for row in cursor.fetchall()]
            
            cursor.execute("SELECT DISTINCT district FROM properties WHERE district IS NOT NULL")
            dist_unicos = [str(row[0]) for row in cursor.fetchall()]
            
            print(f"Departamentos únicos en properties: {len(dept_unicos)}")
            print(f"Provincias únicas en properties: {len(prov_unicos)}")
            print(f"Distritos únicos en properties: {len(dist_unicos)}")
            
            # Verificar cuáles no tienen mapeo
            dept_sin_mapeo = [dept for dept in dept_unicos if dept not in mapeo_departamentos]
            prov_sin_mapeo = [prov for prov in prov_unicos if prov not in mapeo_provincias]
            dist_sin_mapeo = [dist for dist in dist_unicos if dist not in mapeo_distritos]
            
            print(f"\nDepartamentos sin mapeo: {len(dept_sin_mapeo)}")
            if dept_sin_mapeo:
                print(f"  Ejemplos: {dept_sin_mapeo[:5]}")
            
            print(f"Provincias sin mapeo: {len(prov_sin_mapeo)}")
            if prov_sin_mapeo:
                print(f"  Ejemplos: {prov_sin_mapeo[:5]}")
            
            print(f"Distritos sin mapeo: {len(dist_sin_mapeo)}")
            if dist_sin_mapeo:
                print(f"  Ejemplos: {dist_sin_mapeo[:10]}")
            
            # 5. Crear estructura de mapeo completa
            mapeos = {
                'departamentos': mapeo_departamentos,
                'provincias': mapeo_provincias,
                'distritos': mapeo_distritos,
                'sin_mapeo': {
                    'departamentos': dept_sin_mapeo,
                    'provincias': prov_sin_mapeo,
                    'distritos': dist_sin_mapeo
                },
                'estadisticas': {
                    'total_departamentos': len(mapeo_departamentos),
                    'total_provincias': len(mapeo_provincias),
                    'total_distritos': len(mapeo_distritos),
                    'departamentos_unicos_properties': len(dept_unicos),
                    'provincias_unicas_properties': len(prov_unicos),
                    'distritos_unicos_properties': len(dist_unicos)
                }
            }
            
            # 6. Guardar mapeo en archivo JSON
            archivo_mapeo = 'mapeo_ubicaciones_propifai.json'
            with open(archivo_mapeo, 'w', encoding='utf-8') as f:
                json.dump(mapeos, f, ensure_ascii=False, indent=2)
            
            print(f"\n5. MAPEO GUARDADO:")
            print("-" * 50)
            print(f"Archivo: {archivo_mapeo}")
            print(f"Tamaño: {len(json.dumps(mapeos, ensure_ascii=False))} bytes")
            
            # 7. Crear también un módulo Python para fácil importación
            modulo_python = 'propifai/mapeo_ubicaciones.py'
            with open(modulo_python, 'w', encoding='utf-8') as f:
                f.write('''"""
Mapeo de ubicaciones para Propifai.
Generado automáticamente por crear_mapeo_ubicaciones.py
NO MODIFICAR MANUALMENTE - Regenerar con el script si cambian los datos.
"""

# Mapeo de departamentos (ID -> Nombre)
DEPARTAMENTOS = {
''')
                for id_str, nombre in sorted(mapeo_departamentos.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                    f.write(f'    "{id_str}": "{nombre}",\n')
                f.write('''}

# Mapeo de provincias (ID -> Nombre)
PROVINCIAS = {
''')
                for id_str, nombre in sorted(mapeo_provincias.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                    f.write(f'    "{id_str}": "{nombre}",\n')
                f.write('''}

# Mapeo de distritos (ID -> Nombre)
DISTRITOS = {
''')
                for id_str, nombre in sorted(mapeo_distritos.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                    f.write(f'    "{id_str}": "{nombre}",\n')
                f.write('''}

def obtener_nombre_departamento(id_departamento):
    """Devuelve el nombre del departamento dado su ID."""
    return DEPARTAMENTOS.get(str(id_departamento), str(id_departamento))

def obtener_nombre_provincia(id_provincia):
    """Devuelve el nombre de la provincia dado su ID."""
    return PROVINCIAS.get(str(id_provincia), str(id_provincia))

def obtener_nombre_distrito(id_distrito):
    """Devuelve el nombre del distrito dado su ID."""
    return DISTRITOS.get(str(id_distrito), str(id_distrito))

def obtener_ubicacion_completa(departamento_id, provincia_id, distrito_id):
    """Devuelve una tupla con los nombres completos de la ubicación."""
    return (
        obtener_nombre_departamento(departamento_id),
        obtener_nombre_provincia(provincia_id),
        obtener_nombre_distrito(distrito_id)
    )

def formatear_ubicacion(departamento_id, provincia_id, distrito_id, separador=", "):
    """Devuelve una cadena formateada con la ubicación completa."""
    depto = obtener_nombre_departamento(departamento_id)
    prov = obtener_nombre_provincia(provincia_id)
    dist = obtener_nombre_distrito(distrito_id)
    
    partes = []
    if dist and dist != str(distrito_id):
        partes.append(dist)
    if prov and prov != str(provincia_id):
        partes.append(prov)
    if depto and depto != str(departamento_id):
        partes.append(depto)
    
    return separador.join(partes) if partes else f"Distrito {distrito_id}, Provincia {provincia_id}, Departamento {departamento_id}"
''')
            
            print(f"Módulo Python: {modulo_python}")
            
            return mapeos
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {}

if __name__ == '__main__':
    crear_mapeo_completo()