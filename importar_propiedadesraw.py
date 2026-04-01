"""
Script para importar propiedades desde el archivo Excel propiedadesraw_para_azure.xlsx
a la tabla PropiedadRaw de la base de datos.
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from ingestas.models import PropiedadRaw

def limpiar_valor(valor, tipo='str'):
    """Limpia y convierte valores según el tipo esperado."""
    if pd.isna(valor):
        return None
    
    if tipo == 'str':
        return str(valor).strip() if str(valor).strip() != 'nan' else None
    elif tipo == 'int':
        try:
            return int(float(valor))
        except (ValueError, TypeError):
            return None
    elif tipo == 'float':
        try:
            return float(valor)
        except (ValueError, TypeError):
            return None
    elif tipo == 'decimal':
        try:
            return float(valor)
        except (ValueError, TypeError):
            return None
    elif tipo == 'date':
        try:
            # Intentar parsear fecha en varios formatos
            if isinstance(valor, str):
                # Formato YYYY-MM-DD
                if len(valor) == 10 and valor[4] == '-' and valor[7] == '-':
                    return datetime.strptime(valor, '%Y-%m-%d').date()
                # Formato DD/MM/YYYY
                elif len(valor) == 10 and valor[2] == '/' and valor[5] == '/':
                    return datetime.strptime(valor, '%d/%m/%Y').date()
            # Si es datetime de pandas
            elif hasattr(valor, 'date'):
                return valor.date()
        except (ValueError, TypeError):
            return None
    return valor

def importar_propiedades():
    """Importa todas las propiedades desde el archivo Excel."""
    
    # Ruta al archivo Excel
    excel_path = 'requerimientos/data/propiedadesraw_para_azure.xlsx'
    
    if not os.path.exists(excel_path):
        print(f"Error: No se encuentra el archivo {excel_path}")
        return False
    
    print(f"Cargando datos desde {excel_path}...")
    df = pd.read_excel(excel_path)
    print(f"Total de registros en Excel: {len(df)}")
    
    # Contadores
    total_importados = 0
    total_errores = 0
    total_duplicados = 0
    
    # Procesar cada fila
    for index, row in df.iterrows():
        try:
            # Verificar si ya existe un registro con el mismo identificador_externo
            identificador = limpiar_valor(row.get('identificador_externo'), 'str')
            if identificador:
                existe = PropiedadRaw.objects.filter(identificador_externo=identificador).exists()
                if existe:
                    print(f"  Registro {index+1}: Duplicado (identificador_externo={identificador})")
                    total_duplicados += 1
                    continue
            
            # Crear instancia del modelo
            propiedad = PropiedadRaw()
            
            # Mapear campos directos
            propiedad.fuente_excel = limpiar_valor(row.get('fuente_excel'), 'str') or 'propiedadesraw_para_azure.xlsx'
            propiedad.tipo_propiedad = limpiar_valor(row.get('tipo_propiedad'), 'str')
            propiedad.subtipo_propiedad = limpiar_valor(row.get('subtipo_propiedad'), 'str')
            
            # Precio USD - convertir a Decimal
            precio = limpiar_valor(row.get('precio_usd'), 'decimal')
            if precio is not None:
                propiedad.precio_usd = precio
            
            propiedad.descripcion = limpiar_valor(row.get('descripcion'), 'str')
            propiedad.portal = limpiar_valor(row.get('portal'), 'str')
            propiedad.url_propiedad = limpiar_valor(row.get('url_propiedad'), 'str')
            propiedad.coordenadas = limpiar_valor(row.get('coordenadas'), 'str')
            propiedad.departamento = limpiar_valor(row.get('departamento'), 'str')
            propiedad.provincia = limpiar_valor(row.get('provincia'), 'str')
            propiedad.distrito = limpiar_valor(row.get('distrito'), 'str')
            
            # Campos numéricos
            area_terreno = limpiar_valor(row.get('area_terreno'), 'decimal')
            if area_terreno is not None:
                propiedad.area_terreno = area_terreno
            
            area_construida = limpiar_valor(row.get('area_construida'), 'decimal')
            if area_construida is not None:
                propiedad.area_construida = area_construida
            
            numero_pisos = limpiar_valor(row.get('numero_pisos'), 'int')
            if numero_pisos is not None:
                propiedad.numero_pisos = numero_pisos
            
            numero_habitaciones = limpiar_valor(row.get('numero_habitaciones'), 'int')
            if numero_habitaciones is not None:
                propiedad.numero_habitaciones = numero_habitaciones
            
            numero_banos = limpiar_valor(row.get('numero_banos'), 'int')
            if numero_banos is not None:
                propiedad.numero_banos = numero_banos
            
            numero_cocheras = limpiar_valor(row.get('numero_cocheras'), 'int')
            if numero_cocheras is not None:
                propiedad.numero_cocheras = numero_cocheras
            
            propiedad.agente_inmobiliario = limpiar_valor(row.get('agente_inmobiliario'), 'str')
            propiedad.imagenes_propiedad = limpiar_valor(row.get('imagenes_propiedad'), 'str')
            
            # Identificador externo
            if identificador:
                propiedad.identificador_externo = identificador
            
            # Fecha de publicación
            fecha_pub = limpiar_valor(row.get('fecha_publicacion'), 'date')
            if fecha_pub:
                propiedad.fecha_publicacion = fecha_pub
            
            propiedad.antiguedad = limpiar_valor(row.get('antiguedad'), 'str')
            propiedad.servicio_agua = limpiar_valor(row.get('servicio_agua'), 'str')
            propiedad.energia_electrica = limpiar_valor(row.get('energia_electrica'), 'str')
            propiedad.servicio_drenaje = limpiar_valor(row.get('servicio_drenaje'), 'str')
            propiedad.servicio_gas = limpiar_valor(row.get('servicio_gas'), 'str')
            
            # Teléfono agente - convertir a string
            telefono = limpiar_valor(row.get('telefono_agente'), 'str')
            if telefono:
                propiedad.telefono_agente = str(telefono).split('.')[0] if '.' in str(telefono) else str(telefono)
            
            propiedad.estado_propiedad = limpiar_valor(row.get('estado_propiedad'), 'str') or 'en_publicacion'
            
            # Campos adicionales en atributos_extras
            atributos_extras = {}
            operacion = limpiar_valor(row.get('operacion'), 'str')
            if operacion:
                atributos_extras['operacion'] = operacion
            
            if atributos_extras:
                propiedad.atributos_extras = atributos_extras
            
            # Guardar en la base de datos
            propiedad.save()
            total_importados += 1
            
            if (index + 1) % 100 == 0:
                print(f"  Procesados {index + 1} registros...")
                
        except Exception as e:
            print(f"  Error en registro {index + 1}: {str(e)}")
            total_errores += 1
            continue
    
    # Resumen
    print("\n=== RESUMEN DE IMPORTACIÓN ===")
    print(f"Total procesados: {len(df)}")
    print(f"Importados exitosamente: {total_importados}")
    print(f"Duplicados omitidos: {total_duplicados}")
    print(f"Errores: {total_errores}")
    
    # Verificar total en base de datos
    total_en_bd = PropiedadRaw.objects.count()
    print(f"Total registros en base de datos después de importación: {total_en_bd}")
    
    return total_importados > 0

if __name__ == '__main__':
    print("=== IMPORTADOR DE PROPIEDADES RAW ===")
    print("Este script importará datos desde propiedadesraw_para_azure.xlsx a la tabla PropiedadRaw")
    print("\nAdvertencia: Esto agregará nuevos registros a la base de datos.")
    
    respuesta = input("¿Continuar con la importación? (s/n): ").strip().lower()
    if respuesta == 's':
        success = importar_propiedades()
        if success:
            print("\n¡Importación completada exitosamente!")
        else:
            print("\nLa importación encontró problemas.")
    else:
        print("Importación cancelada.")