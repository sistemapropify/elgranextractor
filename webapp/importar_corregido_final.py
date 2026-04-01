#!/usr/bin/env python
"""
Script FINAL para importar propiedadesraw_corregido (2).xlsx con manejo de errores.
Asegura que el campo 'condicion' se importe correctamente (venta, alquiler, anticresis).
"""
import os
import sys
import django
import pandas as pd
from django.db import transaction

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

def limpiar_valor_booleano(valor):
    """Convierte varios formatos de texto a booleano."""
    if valor is None:
        return False
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    
    texto = str(valor).strip().lower()
    # Eliminar caracteres extraños
    texto = texto.replace('�', '').replace('"', '').replace("'", "")
    
    if texto in ['true', 't', 'yes', 'y', '1', 'verdadero', 'si', 'sí']:
        return True
    elif texto in ['false', 'f', 'no', 'n', '0', 'falso']:
        return False
    else:
        # Si no se puede determinar, usar False
        return False

def normalizar_condicion(valor):
    """Normaliza los valores de condición: venta, alquiler, anticresis."""
    if valor is None:
        return 'no_especificado'
    
    texto = str(valor).strip().lower()
    
    # Mapeo de variantes
    if texto in ['venta', 'v', 'sale', 'for sale']:
        return 'venta'
    elif texto in ['alquiler', 'alquileres', 'renta', 'rent', 'arriendo', 'alquileres']:
        return 'alquiler'
    elif texto in ['anticresis', 'anticrético', 'anticretico', 'ant']:
        return 'anticresis'
    elif texto in ['no_especificado', 'no especificado', 'none', 'null', '']:
        return 'no_especificado'
    else:
        # Si no coincide, devolver el texto original (limitado a 50 chars)
        return texto[:50]

def main():
    excel_path = os.path.join('requerimientos', 'data', 'propiedadesraw_corregido (2).xlsx')
    
    if not os.path.exists(excel_path):
        print(f"Error: El archivo {excel_path} no existe.")
        sys.exit(1)
    
    print(f"=== IMPORTACIÓN CORREGIDA DE PROPIEDADESRAW ===")
    print(f"Archivo: {excel_path}")
    print("="*60)
    
    # Leer el archivo Excel
    try:
        df = pd.read_excel(excel_path)
        print(f"Filas leídas: {len(df)}")
        print(f"Columnas: {len(df.columns)}")
    except Exception as e:
        print(f"Error al leer el Excel: {e}")
        sys.exit(1)
    
    # Renombrar columnas con espacios al final
    df.columns = [str(col).strip() for col in df.columns]
    
    # Verificar columnas importantes
    columnas_requeridas = ['condicion']
    for col in columnas_requeridas:
        if col not in df.columns:
            print(f"ADVERTENCIA: Columna '{col}' no encontrada en el Excel.")
            df[col] = None
    
    # Procesar cada fila
    registros_exitosos = 0
    registros_fallidos = 0
    errores_detallados = []
    
    print("\nProcesando filas...")
    
    with transaction.atomic():
        for idx, fila in df.iterrows():
            try:
                # Preparar datos
                datos = {}
                
                # Mapear columnas del Excel a campos del modelo
                mapeo = {
                    'fuente_excel': 'fuente_excel',
                    'fecha_ingesta': 'fecha_ingesta',
                    'tipo_propiedad': 'tipo_propiedad',
                    'subtipo_propiedad': 'subtipo_propiedad',
                    'condicion': 'condicion',
                    'precio_usd': 'precio_usd',
                    'descripcion': 'descripcion',
                    'portal': 'portal',
                    'url_propiedad': 'url_propiedad',
                    'coordenadas': 'coordenadas',
                    'departamento': 'departamento',
                    'provincia': 'provincia',
                    'distrito': 'distrito',
                    'area_terreno': 'area_terreno',
                    'area_construida': 'area_construida',
                    'numero_pisos': 'numero_pisos',
                    'numero_habitaciones': 'numero_habitaciones',
                    'numero_banos': 'numero_banos',
                    'numero_cocheras': 'numero_cocheras',
                    'agente_inmobiliario': 'agente_inmobiliario',
                    'imagenes_propiedad': 'imagenes_propiedad',
                    'identificador_externo': 'identificador_externo',
                    'fecha_publicacion': 'fecha_publicacion',
                    'antiguedad': 'antiguedad',
                    'servicio_agua': 'servicio_agua',
                    'energia_electrica': 'energia_electrica',
                    'servicio_drenaje': 'servicio_drenaje',
                    'servicio_gas': 'servicio_gas',
                    'telefono_agente': 'telefono_agente',
                    'estado_propiedad': 'estado_propiedad',
                    'propiedad_verificada': 'propiedad_verificada'
                }
                
                for col_excel, campo_modelo in mapeo.items():
                    if col_excel in df.columns:
                        valor = fila[col_excel] if pd.notna(fila[col_excel]) else None
                        
                        # Procesamiento especial para ciertos campos
                        if campo_modelo == 'condicion' and valor is not None:
                            valor = normalizar_condicion(valor)
                        elif campo_modelo == 'propiedad_verificada':
                            valor = limpiar_valor_booleano(valor)
                        
                        datos[campo_modelo] = valor
                
                # Crear o actualizar registro
                identificador = datos.get('identificador_externo')
                if identificador:
                    # Intentar actualizar si existe
                    obj, created = PropiedadRaw.objects.update_or_create(
                        identificador_externo=identificador,
                        defaults=datos
                    )
                else:
                    # Crear nuevo
                    obj = PropiedadRaw.objects.create(**datos)
                    created = True
                
                registros_exitosos += 1
                
                if (idx + 1) % 100 == 0:
                    print(f"  Procesadas {idx + 1}/{len(df)} filas...")
                    
            except Exception as e:
                registros_fallidos += 1
                errores_detallados.append(f"Fila {idx + 1}: {str(e)}")
                # Continuar con la siguiente fila
    
    print("\n" + "="*60)
    print("RESUMEN DE IMPORTACIÓN:")
    print(f"- Total filas en Excel: {len(df)}")
    print(f"- Registros exitosos: {registros_exitosos}")
    print(f"- Registros fallidos: {registros_fallidos}")
    
    if registros_fallidos > 0:
        print("\nErrores encontrados (primeros 5):")
        for error in errores_detallados[:5]:
            print(f"  • {error}")
        if len(errores_detallados) > 5:
            print(f"  ... y {len(errores_detallados) - 5} más")
    
    # Estadísticas del campo 'condicion'
    print("\n" + "="*60)
    print("ESTADÍSTICAS DEL CAMPO 'CONDICION':")
    
    try:
        condiciones = PropiedadRaw.objects.values_list('condicion', flat=True).distinct()
        conteo_condiciones = {}
        for cond in condiciones:
            if cond:
                count = PropiedadRaw.objects.filter(condicion=cond).count()
                conteo_condiciones[cond] = count
        
        for cond, count in conteo_condiciones.items():
            print(f"  - {cond}: {count} registros")
    except Exception as e:
        print(f"  Error al obtener estadísticas: {e}")
    
    # Total final
    total_final = PropiedadRaw.objects.count()
    print(f"\nTotal de registros en PropiedadRaw: {total_final}")
    
    print("\n" + "="*60)
    print("IMPORTACIÓN FINALIZADA.")
    
    if registros_exitosos > 0:
        print("✅ La importación se completó con éxito.")
    else:
        print("❌ La importación falló completamente.")
        sys.exit(1)

if __name__ == '__main__':
    main()