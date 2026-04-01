#!/usr/bin/env python
"""
Script para verificar que los cambios en admin.py y templates se han aplicado correctamente.
"""

import os
import sys
import django
from django.test import Client
from django.urls import reverse

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def verificar_admin():
    print("=== VERIFICACIÓN DE CAMBIOS EN ADMIN ===\n")
    
    # Importar el admin después de configurar Django
    from ingestas.admin import PropiedadRawAdmin
    
    admin_instance = PropiedadRawAdmin(model=None, admin_site=None)
    
    print("1. Verificando list_display...")
    list_display = admin_instance.list_display
    campos_requeridos = ['condicion', 'propiedad_verificada']
    
    for campo in campos_requeridos:
        if campo in list_display:
            print(f"  ✓ '{campo}' está en list_display")
        else:
            print(f"  ✗ '{campo}' NO está en list_display")
    
    print("\n2. Verificando list_filter...")
    list_filter = admin_instance.list_filter
    for campo in campos_requeridos:
        if campo in list_filter:
            print(f"  ✓ '{campo}' está en list_filter")
        else:
            print(f"  ✗ '{campo}' NO está en list_filter")
    
    print("\n3. Verificando fieldsets...")
    fieldsets = admin_instance.fieldsets
    campos_en_fieldsets = False
    for _, fieldset in fieldsets:
        if 'condicion' in fieldset['fields'] and 'propiedad_verificada' in fieldset['fields']:
            campos_en_fieldsets = True
            break
    
    if campos_en_fieldsets:
        print("  ✓ 'condicion' y 'propiedad_verificada' están en fieldsets")
    else:
        print("  ✗ Campos no encontrados en fieldsets")
        # Mostrar fieldsets para debug
        for name, data in fieldsets:
            print(f"    - {name}: {data['fields']}")

def verificar_templates():
    print("\n=== VERIFICACIÓN DE CAMBIOS EN TEMPLATES ===\n")
    
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates', 'ingestas')
    
    # Verificar lista_propiedades_rediseno.html
    lista_path = os.path.join(templates_dir, 'lista_propiedades_rediseno.html')
    if os.path.exists(lista_path):
        with open(lista_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        if 'propiedad.get_condicion_display' in contenido:
            print("  ✓ Template lista_propiedades_rediseno.html incluye 'condicion'")
        else:
            print("  ✗ 'condicion' no encontrado en lista_propiedades_rediseno.html")
            
        if 'propiedad.propiedad_verificada' in contenido:
            print("  ✓ Template lista_propiedades_rediseno.html incluye 'propiedad_verificada'")
        else:
            print("  ✗ 'propiedad_verificada' no encontrado en lista_propiedades_rediseno.html")
    else:
        print("  ✗ Template lista_propiedades_rediseno.html no encontrado")
    
    # Verificar detalle_propiedad.html
    detalle_path = os.path.join(templates_dir, 'detalle_propiedad.html')
    if os.path.exists(detalle_path):
        with open(detalle_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        if 'propiedad.get_condicion_display' in contenido or 'propiedad.condicion' in contenido:
            print("  ✓ Template detalle_propiedad.html incluye 'condicion'")
        else:
            print("  ✗ 'condicion' no encontrado en detalle_propiedad.html")
            
        if 'propiedad.propiedad_verificada' in contenido:
            print("  ✓ Template detalle_propiedad.html incluye 'propiedad_verificada'")
        else:
            print("  ✗ 'propiedad_verificada' no encontrado en detalle_propiedad.html")
    else:
        print("  ✗ Template detalle_propiedad.html no encontrado")

def verificar_base_datos():
    print("\n=== VERIFICACIÓN DE BASE DE DATOS ===\n")
    
    from django.db import connection
    
    try:
        with connection.cursor() as cursor:
            # Buscar tabla propiedadraw
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME LIKE '%propiedadraw%'
            """)
            tablas = cursor.fetchall()
            
            if tablas:
                for schema, tabla in tablas:
                    print(f"Tabla: {schema}.{tabla}")
                    
                    for col in ['condicion', 'propiedad_verificada']:
                        cursor.execute("""
                            SELECT COUNT(*)
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? AND COLUMN_NAME = ?
                        """, [schema, tabla, col])
                        existe = cursor.fetchone()[0] > 0
                        
                        if existe:
                            print(f"    ✓ Columna '{col}' EXISTE en la base de datos")
                        else:
                            print(f"    ✗ Columna '{col}' NO EXISTE en la base de datos")
            else:
                print("  ✗ No se encontró la tabla propiedadraw")
    except Exception as e:
        print(f"  ✗ Error al verificar base de datos: {e}")

def main():
    print("=== VERIFICACIÓN COMPLETA DE CAMBIOS ===\n")
    
    verificar_admin()
    verificar_templates()
    verificar_base_datos()
    
    print("\n=== RESUMEN Y RECOMENDACIONES ===")
    print("\n1. Si todas las verificaciones son exitosas, los cambios están aplicados.")
    print("2. Si faltan columnas en la base de datos, ejecuta:")
    print("   python webapp/crear_migracion_faltante.py")
    print("\n3. Después de asegurar que las columnas existen, reinicia el servidor Django.")
    print("\n4. Accede a las siguientes URLs para verificar:")
    print("   - http://localhost:8000/admin/ingestas/propiedadraw/")
    print("   - http://localhost:8000/ingestas/propiedades/")
    print("   - http://localhost:8000/ingestas/propiedad/<id>/ (detalle)")
    print("\n5. Los campos 'condicion' y 'propiedad_verificada' deberían aparecer en:")
    print("   - Lista del admin (columnas y filtros)")
    print("   - Formulario de edición en admin")
    print("   - Tarjetas de propiedades en el portal")
    print("   - Página de detalle de propiedad")

if __name__ == '__main__':
    main()