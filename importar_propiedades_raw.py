#!/usr/bin/env python
"""
Script para importar propiedades desde el archivo propiedadesraw2_tipificado.xlsx
a la tabla PropiedadRaw en Django.
Prioriza las coordenadas para visualización en mapa.
"""
import pandas as pd
import os
import sys
from datetime import datetime
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def importar_propiedades():
    # Ruta al archivo Excel
    excel_path = os.path.join('webapp', 'requerimientos', 'data', 'propiedadesraw2_tipificado.xlsx')
    
    if not os.path.exists(excel_path):
        print(f"Error: Archivo no encontrado: {excel_path}")
        return
    
    print(f"Leyendo archivo Excel: {excel_path}")
    
    # Leer el archivo Excel
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return
    
    print(f"Total de registros en Excel: {len(df)}")
    print(f"Columnas: {df.columns.tolist()}")
    
    # Mapeo de columnas Excel a campos del modelo
    mapeo_campos = {
        'fuente-excel': 'fuente_excel',
        'Tipo de Propiedad': 'tipo_propiedad',
        'URL de la Propiedad': 'url_propiedad',
        'coordenadas': 'coordenadas',
        'Precio (USD)': 'precio_usd',
        'Departamento': 'departamento',
        'Provincia': 'provincia',
        'Distrito': 'distrito',
        'Área de Terreno (m²)': 'area_terreno',
        'Área Construida (m²)': 'area_construida',
        'Número de Pisos': 'numero_pisos',
        'Número de Habitaciones': 'numero_habitaciones',
        'Número de Baños': 'numero_banos',
        'Número de Cocheras': 'numero_cocheras',
        'Imágenes de la Propiedad': 'imagenes_propiedad',
        'identificador-externo': 'identificador_externo',
        'Fecha de Publicación': 'fecha_publicacion',
        'Descripción Detallada': 'descripcion',
        'Antigüedad': 'antiguedad',
        'Servicio de Agua': 'servicio_agua',
        'Energía Eléctrica': 'energia_electrica',
        'Servicio de Drenaje': 'servicio_drenaje',
        'Servicio de Gas': 'servicio_gas',
        'Agente Inmobiliario': 'agente_inmobiliario',
        'Email del Agente': 'email_agente',
        'Teléfono del Agente': 'telefono_agente',
        'Oficina RE/MAX': 'oficina_remax'
    }
    
    # Normalizar nombres de columnas (eliminar caracteres especiales)
    df.columns = df.columns.str.replace('�', 'í').str.replace('�', 'ó').str.replace('�', 'á')
    
    # Contadores
    total_importados = 0
    total_actualizados = 0
    total_errores = 0
    
    # Procesar cada fila
    for index, row in df.iterrows():
        try:
            # Verificar si ya existe una propiedad con el mismo identificador_externo
            identificador = row.get('identificador-externo') or row.get('identificador_externo')
            
            if pd.isna(identificador) or not identificador:
                # Si no hay identificador, usar combinación de coordenadas y URL
                coordenadas = row.get('coordenadas')
                url = row.get('URL de la Propiedad') or row.get('url_propiedad')
                if pd.isna(coordenadas) or not coordenadas:
                    # Si no hay coordenadas, saltar
                    print(f"Fila {index}: Sin identificador ni coordenadas, omitiendo")
                    continue
                
                # Buscar por coordenadas
                propiedad_existente = PropiedadRaw.objects.filter(coordenadas=coordenadas).first()
            else:
                # Buscar por identificador_externo
                propiedad_existente = PropiedadRaw.objects.filter(identificador_externo=identificador).first()
            
            # Preparar datos para crear/actualizar
            datos = {}
            
            for col_excel, campo_modelo in mapeo_campos.items():
                # Normalizar nombre de columna
                col_excel_normalized = col_excel.replace('�', 'í').replace('�', 'ó').replace('�', 'á')
                
                if col_excel_normalized in df.columns:
                    valor = row[col_excel_normalized]
                    
                    # Convertir NaN a None
                    if pd.isna(valor):
                        valor = None
                    
                    # Conversiones específicas
                    if campo_modelo == 'precio_usd' and valor is not None:
                        try:
                            valor = float(valor)
                        except:
                            valor = None
                    
                    if campo_modelo in ['area_terreno', 'area_construida'] and valor is not None:
                        try:
                            valor = float(valor)
                        except:
                            valor = None
                    
                    if campo_modelo in ['numero_pisos', 'numero_habitaciones', 'numero_banos', 'numero_cocheras'] and valor is not None:
                        try:
                            valor = int(float(valor))
                        except:
                            valor = None
                    
                    if campo_modelo == 'fecha_publicacion' and valor is not None:
                        try:
                            if isinstance(valor, datetime):
                                valor = valor.date()
                            elif isinstance(valor, str):
                                valor = datetime.strptime(valor, '%Y-%m-%d').date()
                        except:
                            valor = None
                    
                    datos[campo_modelo] = valor
            
            # Priorizar coordenadas - asegurar que se guarden
            if 'coordenadas' in datos and datos['coordenadas']:
                # Limpiar coordenadas
                coords = str(datos['coordenadas']).strip()
                if coords and coords != 'nan':
                    datos['coordenadas'] = coords
                else:
                    datos['coordenadas'] = None
            
            # Si no hay coordenadas pero hay departamento/distrito, intentar generar coordenadas aproximadas
            if not datos.get('coordenadas') and datos.get('departamento') and datos.get('distrito'):
                # Podríamos agregar lógica para geocodificación aquí
                pass
            
            if propiedad_existente:
                # Actualizar propiedad existente
                for campo, valor in datos.items():
                    if valor is not None:
                        setattr(propiedad_existente, campo, valor)
                propiedad_existente.save()
                total_actualizados += 1
                print(f"Fila {index}: Propiedad actualizada (ID: {propiedad_existente.id})")
            else:
                # Crear nueva propiedad
                nueva_propiedad = PropiedadRaw(**datos)
                nueva_propiedad.save()
                total_importados += 1
                print(f"Fila {index}: Nueva propiedad creada (ID: {nueva_propiedad.id})")
                
        except Exception as e:
            total_errores += 1
            print(f"Error en fila {index}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*50)
    print("RESUMEN DE IMPORTACIÓN")
    print(f"Total procesado: {len(df)}")
    print(f"Nuevas propiedades creadas: {total_importados}")
    print(f"Propiedades actualizadas: {total_actualizados}")
    print(f"Errores: {total_errores}")
    print("="*50)
    
    # Mostrar estadísticas de coordenadas
    propiedades_con_coordenadas = PropiedadRaw.objects.filter(coordenadas__isnull=False).exclude(coordenadas='').count()
    total_propiedades = PropiedadRaw.objects.count()
    print(f"\nPropiedades con coordenadas en la base de datos: {propiedades_con_coordenadas}/{total_propiedades}")
    
    if propiedades_con_coordenadas > 0:
        print("¡Las coordenadas están listas para visualización en mapa!")
    else:
        print("ADVERTENCIA: No hay propiedades con coordenadas. El mapa no mostrará marcadores.")

if __name__ == '__main__':
    importar_propiedades()