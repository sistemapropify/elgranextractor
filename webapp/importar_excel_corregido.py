#!/usr/bin/env python
"""
Script para importar el archivo Excel 'propiedadesraw_corregido (2).xlsx' a la tabla PropiedadRaw.
Este script utiliza el comando de gestión existente y asigna valores por defecto para los campos nuevos:
- condicion: si no existe columna, se asigna 'no_especificado'
- propiedad_verificada: se asigna False

Ejecutar desde la carpeta webapp:
    python importar_excel_corregido.py
"""

import os
import sys
import django
import pandas as pd
from django.core.management import call_command
from django.db import transaction

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

def main():
    excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')
    
    if not os.path.exists(excel_path):
        print(f"Error: El archivo {excel_path} no existe.")
        sys.exit(1)
    
    print(f"Leyendo archivo Excel: {excel_path}")
    
    # Primero, inspeccionar columnas
    try:
        df = pd.read_excel(excel_path, nrows=0)  # Solo leer encabezados
    except Exception as e:
        print(f"Error al leer el Excel: {e}")
        sys.exit(1)
    
    columnas = df.columns.tolist()
    print(f"Columnas encontradas ({len(columnas)}):")
    for col in columnas:
        print(f"  - {col}")
    
    # Verificar si existe columna para 'condicion'
    posibles_nombres = ['condicion', 'Condición', 'Operación', 'Venta/Alquiler', 'Tipo Operación', 'condición']
    col_condicion = None
    for col in columnas:
        if str(col).strip().lower() in [n.lower() for n in posibles_nombres]:
            col_condicion = col
            print(f"  -> Columna para condición encontrada: '{col}'")
            break
    
    if col_condicion is None:
        print("  -> No se encontró columna para 'condicion'. Se asignará 'no_especificado' por defecto.")
    
    # Verificar si existe columna para 'propiedad_verificada'
    col_verificada = None
    for col in columnas:
        if 'verificada' in str(col).lower():
            col_verificada = col
            print(f"  -> Columna para propiedad_verificada encontrada: '{col}'")
            break
    
    if col_verificada is None:
        print("  -> No se encontró columna para 'propiedad_verificada'. Se asignará False por defecto.")
    
    print("\nIniciando importación con el comando de Django...")
    
    # Ejecutar el comando de gestión
    try:
        call_command(
            'importar_excel_propiedadraw',
            excel_path,
            fuente='excel_corregido',
            skip_errors=True,
            dry_run=False
        )
        print("\n¡Importación completada exitosamente!")
        
        # Si no había columna de condición, actualizar registros recién importados
        if col_condicion is None:
            print("Actualizando campo 'condicion' a 'no_especificado' para registros sin valor...")
            updated = PropiedadRaw.objects.filter(condicion__isnull=True).update(condicion='no_especificado')
            print(f"  -> {updated} registros actualizados.")
        
        # Si no había columna de propiedad_verificada, establecer en False
        if col_verificada is None:
            print("Actualizando campo 'propiedad_verificada' a False para registros sin valor...")
            updated = PropiedadRaw.objects.filter(propiedad_verificada__isnull=True).update(propiedad_verificada=False)
            print(f"  -> {updated} registros actualizados.")
        
        # Contar total de registros
        total = PropiedadRaw.objects.count()
        print(f"\nTotal de registros en PropiedadRaw: {total}")
        
    except Exception as e:
        print(f"Error durante la importación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()