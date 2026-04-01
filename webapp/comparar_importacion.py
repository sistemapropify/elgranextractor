#!/usr/bin/env python
"""
Comparar el Excel original con lo importado a la base de datos.
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
    
    print("=== COMPARACIÓN EXCEL vs BASE DE DATOS ===")
    
    # Leer Excel
    df_excel = pd.read_excel(excel_path)
    print(f"1. EXCEL: {len(df_excel)} registros totales")
    
    # Contar por condición en Excel
    if 'condicion' in df_excel.columns:
        cond_excel = df_excel['condicion'].value_counts(dropna=False)
        print("\n   Distribución en Excel:")
        for val, count in cond_excel.items():
            print(f"     '{val}': {count}")
    else:
        print("   ERROR: No hay columna 'condicion' en Excel")
    
    # Obtener datos de la base de datos
    total_db = PropiedadRaw.objects.count()
    print(f"\n2. BASE DE DATOS: {total_db} registros importados")
    
    # Distribución en BD
    from django.db.models import Count
    cond_db = PropiedadRaw.objects.values('condicion').annotate(count=Count('condicion'))
    print("\n   Distribución en Base de Datos:")
    for item in cond_db:
        print(f"     '{item['condicion']}': {item['count']}")
    
    # Calcular diferencia
    diferencia = len(df_excel) - total_db
    print(f"\n3. DIFERENCIA: {diferencia} registros NO importados")
    
    if diferencia > 0:
        print("\n   Posibles causas:")
        print("   - Errores de validación (campos requeridos nulos)")
        print("   - Problemas con tipos de datos")
        print("   - Duplicados que se omitieron")
        
        # Verificar primeros registros no importados
        print("\n   Verificando primeros registros del Excel...")
        for idx, row in df_excel.head(5).iterrows():
            tiene_condicion = row.get('condicion', 'NO EXISTE')
            print(f"     Fila {idx+1}: condicion='{tiene_condicion}'")
    
    # Verificar específicamente registros con "alquiler"
    print("\n4. REGISTROS CON 'ALQUILER' EN EXCEL:")
    if 'condicion' in df_excel.columns:
        alquiler_excel = df_excel[df_excel['condicion'].astype(str).str.contains('alquiler', case=False, na=False)]
        print(f"   En Excel: {len(alquiler_excel)} registros con 'alquiler'")
        
        # Verificar si alguno se importó
        if len(alquiler_excel) > 0:
            print("   Primeros 3 registros 'alquiler' en Excel:")
            for idx, row in alquiler_excel.head(3).iterrows():
                print(f"     Fila {idx+1}: condicion='{row['condicion']}'")
    
    # Verificar registros con "venta"
    print("\n5. REGISTROS CON 'VENTA' EN EXCEL:")
    if 'condicion' in df_excel.columns:
        venta_excel = df_excel[df_excel['condicion'].astype(str).str.contains('venta', case=False, na=False)]
        print(f"   En Excel: {len(venta_excel)} registros con 'venta'")
    
    print("\n" + "="*60)
    print("RECOMENDACIÓN:")
    if diferencia > 0:
        print(f"Necesitas importar los {diferencia} registros faltantes.")
        print("Revisa los errores de validación en los scripts anteriores.")
    else:
        print("Todos los registros del Excel fueron importados.")
        print("Revisa si hay problemas con los valores de 'condicion'.")

if __name__ == '__main__':
    main()