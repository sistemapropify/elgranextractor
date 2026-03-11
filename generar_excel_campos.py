#!/usr/bin/env python
"""
Script para generar un archivo CSV con todos los campos del modelo PropiedadRaw.
"""
import os
import sys
import csv
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def generar_csv():
    campos = []
    for field in PropiedadRaw._meta.get_fields():
        if field.is_relation:
            tipo = "Relación"
            relacion = f"{field.related_model.__name__}"
        else:
            tipo = field.__class__.__name__
            relacion = ""
        
        # Información del campo
        info = {
            'nombre': field.name,
            'tipo': tipo,
            'relacion': relacion,
            'max_length': getattr(field, 'max_length', ''),
            'null': 'Sí' if getattr(field, 'null', False) else 'No',
            'blank': 'Sí' if getattr(field, 'blank', False) else 'No',
            'verbose_name': getattr(field, 'verbose_name', ''),
            'db_column': getattr(field, 'db_column', ''),
            'help_text': getattr(field, 'help_text', ''),
            'choices': '; '.join([c[0] for c in getattr(field, 'choices', [])]),
            'default': str(getattr(field, 'default', '')) if hasattr(field, 'default') else ''
        }
        campos.append(info)
    
    # Ordenar por nombre
    campos.sort(key=lambda x: x['nombre'])
    
    # Escribir CSV
    nombre_archivo = 'campos_propiedadraw.csv'
    with open(nombre_archivo, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['nombre', 'tipo', 'relacion', 'max_length', 'null', 'blank', 
                     'verbose_name', 'db_column', 'help_text', 'choices', 'default']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for campo in campos:
            writer.writerow(campo)
    
    print(f"Archivo CSV generado: {nombre_archivo}")
    print(f"Total de campos: {len(campos)}")
    
    # Mostrar vista previa
    print("\n--- VISTA PREVIA (primeros 5 campos) ---")
    with open(nombre_archivo, 'r', encoding='utf-8') as f:
        lines = f.readlines()[:6]
        for line in lines:
            print(line.strip())

if __name__ == '__main__':
    try:
        generar_csv()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)