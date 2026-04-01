#!/usr/bin/env python
"""
Script simple para importar propiedades desde Excel a PropiedadRaw.
"""
import os
import sys
import pandas as pd

# Configurar Django - estamos ejecutando desde el directorio webapp (por el cd webapp)
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from ingestas.models import PropiedadRaw

def main():
    # Cargar el archivo Excel
    excel_path = 'requerimientos/data/propiedadesraw_para_azure.xlsx'
    print(f"Cargando datos desde {excel_path}...")
    
    if not os.path.exists(excel_path):
        print(f"Error: No se encuentra el archivo {excel_path}")
        return
    
    df = pd.read_excel(excel_path)
    print(f"Total de registros en Excel: {len(df)}")
    
    # Verificar estado actual
    count_before = PropiedadRaw.objects.count()
    print(f"Registros en base de datos antes: {count_before}")
    
    # Procesar todos los registros
    imported = 0
    errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Verificar si ya existe por identificador_externo
            identificador = str(row.get('identificador_externo', '')).strip()
            if identificador and identificador != 'nan':
                if PropiedadRaw.objects.filter(identificador_externo=identificador).exists():
                    continue  # Saltar duplicados
            
            # Crear nueva propiedad
            propiedad = PropiedadRaw()
            
            # Campos básicos
            propiedad.fuente_excel = 'propiedadesraw_para_azure.xlsx'
            
            # Campos de texto
            text_fields = [
                'tipo_propiedad', 'subtipo_propiedad', 'descripcion', 'portal',
                'url_propiedad', 'coordenadas', 'departamento', 'provincia',
                'distrito', 'agente_inmobiliario', 'imagenes_propiedad',
                'antiguedad', 'servicio_agua', 'energia_electrica',
                'servicio_drenaje', 'servicio_gas', 'estado_propiedad'
            ]
            
            for field in text_fields:
                if field in row and pd.notna(row[field]):
                    setattr(propiedad, field, str(row[field]).strip())
            
            # Campos numéricos
            numeric_fields = [
                'precio_usd', 'area_terreno', 'area_construida',
                'numero_pisos', 'numero_habitaciones', 'numero_banos', 'numero_cocheras'
            ]
            
            for field in numeric_fields:
                if field in row and pd.notna(row[field]):
                    try:
                        setattr(propiedad, field, float(row[field]))
                    except:
                        pass
            
            # Identificador externo
            if identificador and identificador != 'nan':
                propiedad.identificador_externo = identificador
            
            # Teléfono
            if 'telefono_agente' in row and pd.notna(row['telefono_agente']):
                propiedad.telefono_agente = str(row['telefono_agente']).split('.')[0]
            
            # Fecha de publicación (simplificado)
            if 'fecha_publicacion' in row and pd.notna(row['fecha_publicacion']):
                try:
                    if hasattr(row['fecha_publicacion'], 'date'):
                        propiedad.fecha_publicacion = row['fecha_publicacion'].date()
                except:
                    pass
            
            # Guardar
            propiedad.save()
            imported += 1
            
            if imported % 100 == 0:
                print(f"  Importados {imported} registros...")
                
        except Exception as e:
            errors += 1
            if errors <= 5:  # Mostrar solo primeros 5 errores
                print(f"  Error en fila {idx}: {e}")
    
    # Resumen
    count_after = PropiedadRaw.objects.count()
    print(f"\n=== RESUMEN ===")
    print(f"Registros antes: {count_before}")
    print(f"Registros importados: {imported}")
    print(f"Errores: {errors}")
    print(f"Registros después: {count_after}")
    print(f"Total esperado: {len(df)} registros en Excel")

if __name__ == '__main__':
    main()