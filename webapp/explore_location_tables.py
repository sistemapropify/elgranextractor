#!/usr/bin/env python
"""
Script para explorar las tablas de ubicación en la base de datos Propifai.
"""
import os
import sys
import django
from django.db import connections

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def explorar_tablas_ubicacion():
    print("EXPLORANDO TABLAS DE UBICACIÓN EN PROPIFAI")
    print("=" * 70)
    
    # Conectar a la base de datos propifai
    connection = connections['propifai']
    
    try:
        with connection.cursor() as cursor:
            # 1. Explorar tabla departments
            print("\n1. TABLA 'departments':")
            print("-" * 50)
            cursor.execute("SELECT TOP 10 id, name FROM departments ORDER BY id")
            departamentos = cursor.fetchall()
            print(f"Total de departamentos (primeros 10): {len(departamentos)}")
            for id_depto, nombre in departamentos:
                print(f"  ID: {id_depto}, Nombre: {nombre}")
            
            # 2. Explorar tabla properties_province
            print("\n2. TABLA 'properties_province':")
            print("-" * 50)
            cursor.execute("SELECT TOP 10 id, name FROM properties_province ORDER BY id")
            provincias = cursor.fetchall()
            print(f"Total de provincias (primeros 10): {len(provincias)}")
            for id_prov, nombre in provincias:
                print(f"  ID: {id_prov}, Nombre: {nombre}")
            
            # 3. Explorar tabla properties_district
            print("\n3. TABLA 'properties_district':")
            print("-" * 50)
            cursor.execute("SELECT TOP 20 id, name FROM properties_district ORDER BY id")
            distritos = cursor.fetchall()
            print(f"Total de distritos (primeros 20): {len(distritos)}")
            for id_dist, nombre in distritos:
                print(f"  ID: {id_dist}, Nombre: {nombre}")
            
            # 4. Verificar relaciones entre tablas
            print("\n4. RELACIONES ENTRE TABLAS:")
            print("-" * 50)
            
            # Verificar si properties_district tiene provincia_id
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties_district' 
                AND TABLE_SCHEMA = 'dbo'
            """)
            columnas_distrito = cursor.fetchall()
            print("Columnas de properties_district:")
            for col_name, data_type in columnas_distrito:
                print(f"  {col_name} ({data_type})")
            
            # 5. Explorar tabla properties para ver cómo se relacionan
            print("\n5. TABLA 'properties' (campos de ubicación):")
            print("-" * 50)
            
            # Buscar columnas de ubicación en properties
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties' 
                AND TABLE_SCHEMA = 'dbo'
                AND (COLUMN_NAME LIKE '%department%' 
                     OR COLUMN_NAME LIKE '%province%' 
                     OR COLUMN_NAME LIKE '%district%'
                     OR COLUMN_NAME LIKE '%location%')
                ORDER BY COLUMN_NAME
            """)
            columnas_ubic = cursor.fetchall()
            print("Columnas de ubicación en properties:")
            for col_name, data_type in columnas_ubic:
                print(f"  {col_name} ({data_type})")
            
            # 6. Verificar valores reales en properties
            print("\n6. VALORES DE UBICACIÓN EN PROPERTIES (ejemplos):")
            print("-" * 50)
            
            # Obtener algunas propiedades con sus ubicaciones
            cursor.execute("""
                SELECT TOP 5 
                    id, 
                    department_id,
                    province_id,
                    district_id,
                    title
                FROM properties 
                WHERE department_id IS NOT NULL 
                OR province_id IS NOT NULL 
                OR district_id IS NOT NULL
                ORDER BY id
            """)
            propiedades = cursor.fetchall()
            
            for prop in propiedades:
                prop_id, dept_id, prov_id, dist_id, title = prop
                print(f"\n  Propiedad ID: {prop_id}")
                print(f"    Título: {title[:50]}...")
                print(f"    department_id: {dept_id}")
                print(f"    province_id: {prov_id}")
                print(f"    district_id: {dist_id}")
                
                # Buscar nombres correspondientes
                if dept_id:
                    cursor.execute("SELECT name FROM departments WHERE id = %s", [dept_id])
                    dept_nombre = cursor.fetchone()
                    if dept_nombre:
                        print(f"    Departamento: {dept_nombre[0]}")
                
                if prov_id:
                    cursor.execute("SELECT name FROM properties_province WHERE id = %s", [prov_id])
                    prov_nombre = cursor.fetchone()
                    if prov_nombre:
                        print(f"    Provincia: {prov_nombre[0]}")
                
                if dist_id:
                    cursor.execute("SELECT name FROM properties_district WHERE id = %s", [dist_id])
                    dist_nombre = cursor.fetchone()
                    if dist_nombre:
                        print(f"    Distrito: {dist_nombre[0]}")
            
            # 7. Crear mapeo completo
            print("\n7. CREANDO MAPEO COMPLETO:")
            print("-" * 50)
            
            # Mapeo de departamentos
            cursor.execute("SELECT id, name FROM departments")
            mapeo_departamentos = {str(row[0]): row[1] for row in cursor.fetchall()}
            print(f"Mapeo departamentos: {len(mapeo_departamentos)} registros")
            
            # Mapeo de provincias
            cursor.execute("SELECT id, name FROM properties_province")
            mapeo_provincias = {str(row[0]): row[1] for row in cursor.fetchall()}
            print(f"Mapeo provincias: {len(mapeo_provincias)} registros")
            
            # Mapeo de distritos
            cursor.execute("SELECT id, name FROM properties_district")
            mapeo_distritos = {str(row[0]): row[1] for row in cursor.fetchall()}
            print(f"Mapeo distritos: {len(mapeo_distritos)} registros")
            
            # Guardar mapeos en un archivo para uso futuro
            mapeos = {
                'departamentos': mapeo_departamentos,
                'provincias': mapeo_provincias,
                'distritos': mapeo_distritos
            }
            
            import json
            with open('webapp/mapeo_ubicaciones_propifai.json', 'w', encoding='utf-8') as f:
                json.dump(mapeos, f, ensure_ascii=False, indent=2)
            
            print(f"\nMapeos guardados en 'webapp/mapeo_ubicaciones_propifai.json'")
            
            # 8. Verificar distritos numéricos vs nombres
            print("\n8. COMPARACIÓN CON DISTRITOS NUMÉRICOS EN PROPIEDADES:")
            print("-" * 50)
            
            # Obtener todos los district_id únicos de properties
            cursor.execute("SELECT DISTINCT district_id FROM properties WHERE district_id IS NOT NULL")
            district_ids = [str(row[0]) for row in cursor.fetchall()]
            
            print(f"District IDs únicos en properties: {len(district_ids)}")
            print("Ejemplos:")
            for dist_id in sorted(district_ids)[:20]:
                nombre = mapeo_distritos.get(dist_id, 'NO ENCONTRADO')
                print(f"  ID {dist_id}: {nombre}")
            
            # Verificar cuántos no tienen mapeo
            sin_mapeo = [dist_id for dist_id in district_ids if dist_id not in mapeo_distritos]
            print(f"\nDistrict IDs sin mapeo: {len(sin_mapeo)}")
            if sin_mapeo:
                print(f"  Ejemplos: {sin_mapeo[:10]}")
            
            return mapeo_departamentos, mapeo_provincias, mapeo_distritos
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {}, {}, {}

if __name__ == '__main__':
    explorar_tablas_ubicacion()