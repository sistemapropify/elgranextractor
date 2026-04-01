#!/usr/bin/env python
"""
Importación SIMPLE del Excel, manejando el campo propiedad_verificada como texto primero.
"""
import os
import sys
import django
import pandas as pd

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db import transaction

def main():
    excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')
    
    print(f"Importando desde: {excel_path}")
    
    # Leer Excel
    df = pd.read_excel(excel_path)
    print(f"Filas a importar: {len(df)}")
    
    # Limpiar nombres de columnas
    df.columns = [str(col).strip() for col in df.columns]
    
    # Reemplazar NaN por None
    df = df.where(pd.notnull(df), None)
    
    # Contador
    success = 0
    errors = 0
    
    with transaction.atomic():
        for idx, row in df.iterrows():
            try:
                # Preparar datos
                data = {}
                
                # Mapeo simple
                for col in df.columns:
                    if hasattr(PropiedadRaw, col):
                        value = row[col]
                        
                        # Manejo especial para propiedad_verificada
                        if col == 'propiedad_verificada':
                            if value is None:
                                value = False
                            elif isinstance(value, str):
                                value = value.lower().strip() in ['true', '1', 'yes', 'si', 'verdadero']
                            elif isinstance(value, (int, float)):
                                value = bool(value)
                            else:
                                value = False
                        
                        # Manejo especial para condicion
                        if col == 'condicion' and value is not None:
                            value = str(value).strip().lower()
                            # Normalizar
                            if value in ['venta', 'v', 'sale']:
                                value = 'venta'
                            elif value in ['alquiler', 'renta', 'rent', 'alquileres']:
                                value = 'alquiler'
                            elif value in ['anticresis', 'anticrético', 'anticretico']:
                                value = 'anticresis'
                        
                        data[col] = value
                
                # Crear objeto
                PropiedadRaw.objects.create(**data)
                success += 1
                
                if (idx + 1) % 100 == 0:
                    print(f"  Procesadas {idx + 1} filas...")
                    
            except Exception as e:
                errors += 1
                if errors <= 3:  # Mostrar solo primeros 3 errores
                    print(f"  Error en fila {idx + 1}: {e}")
                continue
    
    print("\n" + "="*60)
    print(f"RESULTADO:")
    print(f"  - Importados exitosamente: {success}")
    print(f"  - Errores: {errors}")
    print(f"  - Total en tabla: {PropiedadRaw.objects.count()}")
    
    # Mostrar distribución de condición
    print("\nDistribución de 'condicion':")
    from django.db.models import Count
    for item in PropiedadRaw.objects.values('condicion').annotate(count=Count('condicion')).order_by('-count'):
        print(f"  - {item['condicion']}: {item['count']}")

if __name__ == '__main__':
    main()