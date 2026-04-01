#!/usr/bin/env python
"""
Importación ROBUSTA del Excel - Maneja todos los errores conocidos.
"""
import os
import sys
import django
import pandas as pd
import numpy as np

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db import transaction

def convertir_valor(valor, tipo_campo):
    """Convierte un valor al tipo adecuado para el campo."""
    if pd.isna(valor) or valor is None:
        return None
    
    # Para campos numéricos
    if tipo_campo in ['DecimalField', 'FloatField', 'IntegerField', 'PositiveIntegerField']:
        try:
            # Intentar convertir a número
            if isinstance(valor, str):
                # Limpiar caracteres extraños
                valor = valor.replace('�', '').strip()
                if valor == '':
                    return None
            return float(valor)
        except:
            return None
    
    # Para campos BooleanField
    if tipo_campo == 'BooleanField':
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, (int, float)):
            return bool(valor)
        if isinstance(valor, str):
            valor_str = valor.lower().replace('�', '').strip()
            if valor_str in ['true', '1', 'yes', 'si', 'verdadero', 't']:
                return True
            elif valor_str in ['false', '0', 'no', 'falso', 'f']:
                return False
        return False
    
    # Para campos CharField/TextField
    if tipo_campo in ['CharField', 'TextField', 'URLField', 'EmailField']:
        if isinstance(valor, (int, float)):
            return str(valor)
        return str(valor).strip() if valor else ''
    
    return valor

def main():
    excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')
    
    print(f"=== IMPORTACIÓN ROBUSTA ===")
    print(f"Archivo: {excel_path}")
    
    # Leer Excel
    try:
        df = pd.read_excel(excel_path, dtype=str)  # Leer todo como texto primero
        print(f"Filas leídas: {len(df)}")
    except Exception as e:
        print(f"Error al leer Excel: {e}")
        return
    
    # Limpiar nombres de columnas
    df.columns = [str(col).strip() for col in df.columns]
    
    # Obtener información de campos del modelo
    campos_modelo = {}
    for field in PropiedadRaw._meta.fields:
        campos_modelo[field.name] = field.get_internal_type()
    
    # Contadores
    success = 0
    errors = 0
    error_messages = []
    
    print("\nProcesando filas...")
    
    with transaction.atomic():
        for idx, row in df.iterrows():
            try:
                data = {}
                
                # Procesar cada columna que existe en el modelo
                for col_name in df.columns:
                    if col_name in campos_modelo:
                        valor_raw = row[col_name]
                        tipo_campo = campos_modelo[col_name]
                        
                        # Convertir valor
                        valor_convertido = convertir_valor(valor_raw, tipo_campo)
                        
                        # Manejo especial para 'condicion'
                        if col_name == 'condicion' and valor_convertido:
                            cond = str(valor_convertido).lower().strip()
                            if cond in ['venta', 'v', 'sale']:
                                valor_convertido = 'venta'
                            elif cond in ['alquiler', 'renta', 'rent', 'alquileres']:
                                valor_convertido = 'alquiler'
                            elif cond in ['anticresis', 'anticrético', 'anticretico', 'ant']:
                                valor_convertido = 'anticresis'
                            elif cond in ['', 'nan', 'none', 'null']:
                                valor_convertido = 'no_especificado'
                        
                        data[col_name] = valor_convertido
                
                # Asegurar campos requeridos
                if 'condicion' not in data or not data['condicion']:
                    data['condicion'] = 'no_especificado'
                
                if 'propiedad_verificada' not in data:
                    data['propiedad_verificada'] = False
                
                # Crear registro
                PropiedadRaw.objects.create(**data)
                success += 1
                
                if (idx + 1) % 200 == 0:
                    print(f"  Procesadas {idx + 1}/{len(df)} filas...")
                    
            except Exception as e:
                errors += 1
                error_messages.append(f"Fila {idx + 1}: {str(e)}")
                if errors <= 5:
                    print(f"  Error en fila {idx + 1}: {e}")
                continue
    
    print("\n" + "="*60)
    print("RESULTADO FINAL:")
    print(f"  - Registros importados exitosamente: {success}")
    print(f"  - Errores: {errors}")
    
    total_tabla = PropiedadRaw.objects.count()
    print(f"  - Total en tabla PropiedadRaw: {total_tabla}")
    
    # Estadísticas de condición
    if total_tabla > 0:
        print("\nDISTRIBUCIÓN DE 'CONDICION':")
        from django.db.models import Count
        distribucion = PropiedadRaw.objects.values('condicion').annotate(
            count=Count('condicion')
        ).order_by('-count')
        
        for item in distribucion:
            cond = item['condicion'] or 'NULL'
            count = item['count']
            porcentaje = (count / total_tabla) * 100
            print(f"  - '{cond}': {count} registros ({porcentaje:.1f}%)")
    
    # Mostrar primeros errores si hay muchos
    if errors > 0 and len(error_messages) > 0:
        print(f"\nPRIMEROS 3 ERRORES:")
        for msg in error_messages[:3]:
            print(f"  • {msg}")
    
    print("\n" + "="*60)
    if success > 0:
        print(f"✅ IMPORTACIÓN EXITOSA: {success} registros importados.")
    else:
        print("❌ IMPORTACIÓN FALLIDA: No se importó ningún registro.")
        print("   Revisa los errores anteriores.")

if __name__ == '__main__':
    main()