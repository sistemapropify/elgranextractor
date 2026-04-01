#!/usr/bin/env python
"""
IMPORTACIÓN DEFINITIVA - Maneja todos los campos requeridos y asigna valores por defecto.
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

def main():
    excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')
    
    print("=== IMPORTACIÓN DEFINITIVA DE PROPIEDADESRAW ===")
    print(f"Archivo: {excel_path}")
    
    # Leer Excel
    df = pd.read_excel(excel_path)
    print(f"Total filas en Excel: {len(df)}")
    
    # Limpiar nombres de columnas
    df.columns = [str(col).strip() for col in df.columns]
    
    # Reemplazar NaN con valores por defecto
    df = df.fillna({
        'fuente_excel': 'excel_corregido',
        'condicion': 'no_especificado',
        'propiedad_verificada': False,
        'tipo_propiedad': 'No especificado',
        'departamento': 'No especificado',
        'distrito': 'No especificado'
    })
    
    # Asegurar que los campos requeridos tengan valor
    if 'fuente_excel' not in df.columns:
        df['fuente_excel'] = 'excel_corregido'
    
    # Normalizar condición
    def normalizar_condicion(val):
        if pd.isna(val):
            return 'no_especificado'
        val_str = str(val).lower().strip()
        if val_str in ['venta', 'v', 'sale']:
            return 'venta'
        elif val_str in ['alquiler', 'renta', 'rent', 'alquileres']:
            return 'alquiler'
        elif val_str in ['anticresis', 'anticrético', 'anticretico', 'ant']:
            return 'anticresis'
        else:
            return 'no_especificado'
    
    if 'condicion' in df.columns:
        df['condicion'] = df['condicion'].apply(normalizar_condicion)
    else:
        df['condicion'] = 'no_especificado'
    
    # Convertir propiedad_verificada a booleano
    def a_booleano(val):
        if pd.isna(val):
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        val_str = str(val).lower().strip()
        return val_str in ['true', '1', 'yes', 'si', 'verdadero', 't']
    
    if 'propiedad_verificada' in df.columns:
        df['propiedad_verificada'] = df['propiedad_verificada'].apply(a_booleano)
    else:
        df['propiedad_verificada'] = False
    
    # Procesar fila por fila
    success = 0
    errors = 0
    batch_size = 100
    
    print("\nImportando registros...")
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        batch_records = []
        
        for idx, row in batch.iterrows():
            try:
                # Preparar datos
                data = {}
                
                # Mapear todas las columnas que existen en el modelo
                for col in df.columns:
                    if hasattr(PropiedadRaw, col):
                        value = row[col]
                        if pd.isna(value):
                            value = None
                        data[col] = value
                
                # Campos obligatorios mínimos
                if 'fuente_excel' not in data or not data['fuente_excel']:
                    data['fuente_excel'] = 'excel_corregido'
                
                # Crear objeto (no guardar aún)
                batch_records.append(PropiedadRaw(**data))
                
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  Error preparando fila {idx+1}: {e}")
        
        # Guardar batch
        if batch_records:
            try:
                PropiedadRaw.objects.bulk_create(batch_records, ignore_conflicts=True)
                success += len(batch_records)
                print(f"  Batch {i//batch_size + 1}: {len(batch_records)} registros guardados")
            except Exception as e:
                errors += len(batch_records)
                print(f"  Error en batch {i//batch_size + 1}: {e}")
                # Intentar uno por uno
                for record in batch_records:
                    try:
                        record.save()
                        success += 1
                    except:
                        errors += 1
    
    print("\n" + "="*60)
    print("RESULTADO:")
    print(f"  - Registros importados: {success}")
    print(f"  - Errores: {errors}")
    
    total = PropiedadRaw.objects.count()
    print(f"  - Total en tabla: {total}")
    
    # Estadísticas de condición
    if total > 0:
        print("\nDISTRIBUCIÓN DE CONDICIÓN:")
        from django.db.models import Count
        stats = PropiedadRaw.objects.values('condicion').annotate(
            count=Count('condicion')
        ).order_by('-count')
        
        for stat in stats:
            cond = stat['condicion'] or 'NULL'
            count = stat['count']
            porcentaje = (count / total) * 100
            print(f"  - {cond}: {count} ({porcentaje:.1f}%)")
    
    print("\n" + "="*60)
    if success > 0:
        print("IMPORTACION EXITOSA!")
    else:
        print("IMPORTACION FALLIDA - Revisar errores.")

if __name__ == '__main__':
    main()