#!/usr/bin/env python
"""
Importa requerimientos desde el archivo requerimientos_inmobiliarios.xlsx
a la tabla de Requerimientos en Django.
"""
import pandas as pd
import os
import sys
from datetime import datetime
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento, FuenteChoices, CondicionChoices, \
    TipoPropiedadChoices, MonedaChoices, FormaPagoChoices, TernarioChoices

def mapear_fuente(valor):
    """Mapea el valor de fuente a las opciones del modelo."""
    if not valor or pd.isna(valor):
        return FuenteChoices.OTRO
    valor = str(valor).lower()
    if 'red inmobiliaria' in valor:
        return FuenteChoices.UNIDAS  # Asumimos que es Inmobiliarias Unidas
    return FuenteChoices.OTRO

def mapear_condicion(valor):
    """Mapea condición basado en Tipo Original y Condicion."""
    if not valor or pd.isna(valor):
        return CondicionChoices.NO_ESPECIFICADO
    valor = str(valor).lower()
    if 'compra' in valor:
        return CondicionChoices.COMPRA
    if 'alquiler' in valor:
        return CondicionChoices.ALQUILER
    if 'anticresis' in valor:
        return CondicionChoices.COMPRA  # Asumimos compra para anticresis
    return CondicionChoices.NO_ESPECIFICADO

def mapear_tipo_propiedad(valor):
    """Mapea tipo de propiedad."""
    if not valor or pd.isna(valor):
        return TipoPropiedadChoices.NO_ESPECIFICADO
    valor = str(valor).lower()
    if 'departamento' in valor:
        return TipoPropiedadChoices.DEPARTAMENTO
    if 'casa' in valor:
        return TipoPropiedadChoices.CASA
    if 'terreno' in valor:
        return TipoPropiedadChoices.TERRENO
    if 'local' in valor or 'comercial' in valor:
        return TipoPropiedadChoices.LOCAL_COMERCIAL
    if 'almacén' in valor or 'almacen' in valor:
        return TipoPropiedadChoices.ALMACEN
    if 'oficina' in valor:
        return TipoPropiedadChoices.OFICINA
    if 'proyecto' in valor:
        return TipoPropiedadChoices.NO_ESPECIFICADO  # No hay opción proyecto
    return TipoPropiedadChoices.NO_ESPECIFICADO

def mapear_moneda(valor):
    if not valor or pd.isna(valor):
        return MonedaChoices.NO_ESPECIFICADO
    valor = str(valor).upper()
    if 'USD' in valor:
        return MonedaChoices.USD
    if 'PEN' in valor or 'SOL' in valor:
        return MonedaChoices.PEN
    return MonedaChoices.NO_ESPECIFICADO

def mapear_forma_pago(valor):
    if not valor or pd.isna(valor):
        return FormaPagoChoices.NO_ESPECIFICADO
    valor = str(valor).lower()
    if 'contado' in valor:
        return FormaPagoChoices.CONTADO
    if 'crédito' in valor or 'credito' in valor or 'hipotecario' in valor:
        return FormaPagoChoices.FINANCIADO
    return FormaPagoChoices.NO_ESPECIFICADO

def mapear_ternario(valor):
    if not valor or pd.isna(valor):
        return TernarioChoices.INDIFERENTE
    valor = str(valor).lower()
    if 'si' in valor or 'sí' in valor:
        return TernarioChoices.SI
    if 'no' in valor:
        return TernarioChoices.NO
    return TernarioChoices.INDIFERENTE

def parsear_fecha(valor):
    """Convierte fecha en formato dd/mm/yy a objeto date."""
    if not valor or pd.isna(valor):
        return None
    try:
        # Puede ser datetime, date o string
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, pd.Timestamp):
            return valor.date()
        # String como '12/6/24'
        parts = str(valor).split('/')
        if len(parts) == 3:
            day, month, year = map(int, parts)
            if year < 100:
                year += 2000  # Asumimos años 2000+
            return datetime(year, month, day).date()
    except Exception:
        pass
    return None

def parsear_hora(valor):
    """Convierte hora a objeto time."""
    if not valor or pd.isna(valor):
        return None
    try:
        if isinstance(valor, datetime):
            return valor.time()
        if isinstance(valor, pd.Timestamp):
            return valor.time()
        # String como '10:50'
        from datetime import time
        parts = str(valor).split(':')
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            return time(hour, minute)
    except Exception:
        pass
    return None

def importar_excel(ruta_excel, limite=0):
    """Importa los datos del Excel a la base de datos."""
    print(f"Leyendo archivo: {ruta_excel}")
    
    if not os.path.exists(ruta_excel):
        print(f"Error: Archivo no encontrado: {ruta_excel}")
        return
    
    try:
        df = pd.read_excel(ruta_excel, sheet_name=0, header=0)
    except Exception as e:
        print(f"Error al leer Excel: {e}")
        return
    
    print(f"Filas leídas: {len(df)}")
    print(f"Columnas: {list(df.columns)}")
    
    if limite > 0:
        df = df.head(limite)
        print(f"Procesando solo {limite} filas")
    
    creados = 0
    actualizados = 0
    errores = 0
    
    for idx, row in df.iterrows():
        try:
            # Extraer valores
            fuente_val = row.get('Fuente', '')
            fecha_val = row.get('Fecha')
            hora_val = row.get('Hora')
            agente_val = row.get('Agente', '')
            tipo_original_val = row.get('Tipo Original', '')
            condicion_val = row.get('Condicion', '')
            tipo_propiedad_val = row.get('Tipo Propiedad', '')
            distritos_val = row.get('Distritos', '')
            presupuesto_monto_val = row.get('Presupuesto Monto')
            moneda_val = row.get('Moneda', '')
            forma_pago_val = row.get('Forma Pago', '')
            habitaciones_val = row.get('Habitaciones')
            banos_val = row.get('Banos')
            cochera_val = row.get('Cochera', '')
            ascensor_val = row.get('Ascensor', '')
            amueblado_val = row.get('Amueblado', '')
            area_m2_val = row.get('Area m2')
            piso_preferencia_val = row.get('Piso Preferencia', '')
            caracteristicas_extra_val = row.get('Caracteristicas Extra', '')
            agente_telefono_val = row.get('Tel Agente', '')
            requerimiento_val = row.get('Requerimiento', '')
            
            # Mapear valores
            fuente = mapear_fuente(fuente_val)
            fecha = parsear_fecha(fecha_val)
            hora = parsear_hora(hora_val)
            condicion = mapear_condicion(tipo_original_val)  # Usar Tipo Original para condición
            tipo_propiedad = mapear_tipo_propiedad(tipo_propiedad_val)
            presupuesto_moneda = mapear_moneda(moneda_val)
            presupuesto_forma_pago = mapear_forma_pago(forma_pago_val)
            cochera = mapear_ternario(cochera_val)
            ascensor = mapear_ternario(ascensor_val)
            amueblado = mapear_ternario(amueblado_val)
            
            # Convertir números
            try:
                presupuesto_monto = float(presupuesto_monto_val) if not pd.isna(presupuesto_monto_val) else None
            except:
                presupuesto_monto = None
            
            try:
                habitaciones = int(habitaciones_val) if not pd.isna(habitaciones_val) else None
            except:
                habitaciones = None
            
            try:
                banos = int(banos_val) if not pd.isna(banos_val) else None
            except:
                banos = None
            
            try:
                area_m2 = int(area_m2_val) if not pd.isna(area_m2_val) else None
            except:
                area_m2 = None
            
            # Crear o actualizar requerimiento
            # Usar algún identificador único, por ejemplo combinación de fuente, fecha, hora, agente
            # Para simplificar, siempre creamos nuevo (podría haber duplicados)
            requerimiento = Requerimiento(
                fuente=fuente,
                fecha=fecha,
                hora=hora,
                agente=agente_val[:120],  # Limitar longitud
                tipo_original=tipo_original_val[:80],
                condicion=condicion,
                tipo_propiedad=tipo_propiedad,
                distritos=distritos_val[:300],
                presupuesto_monto=presupuesto_monto,
                presupuesto_moneda=presupuesto_moneda,
                presupuesto_forma_pago=presupuesto_forma_pago,
                habitaciones=habitaciones,
                banos=banos,
                cochera=cochera,
                ascensor=ascensor,
                amueblado=amueblado,
                area_m2=area_m2,
                piso_preferencia=str(piso_preferencia_val)[:60],
                caracteristicas_extra=str(caracteristicas_extra_val)[:300],
                agente_telefono=str(agente_telefono_val)[:20],
                requerimiento=str(requerimiento_val)[:5000],  # Limitar texto largo
            )
            
            requerimiento.save()
            creados += 1
            
            if creados % 50 == 0:
                print(f"  Procesados {creados} registros...")
                
        except Exception as e:
            print(f"Error en fila {idx}: {e}")
            errores += 1
    
    print(f"\nImportación completada:")
    print(f"  Registros creados: {creados}")
    print(f"  Registros actualizados: {actualizados}")
    print(f"  Errores: {errores}")

if __name__ == '__main__':
    ruta = os.path.join('webapp', 'requerimientos', 'data', 'requerimientos_inmobiliarios.xlsx')
    importar_excel(ruta, limite=0)  # 0 para todos