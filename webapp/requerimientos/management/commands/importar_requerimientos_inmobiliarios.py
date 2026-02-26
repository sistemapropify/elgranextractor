import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from requerimientos.models import Requerimiento, FuenteChoices, CondicionChoices, \
    TipoPropiedadChoices, MonedaChoices, FormaPagoChoices, TernarioChoices
import os
import sys
from datetime import datetime

class Command(BaseCommand):
    help = 'Importa requerimientos desde el archivo requerimientos_inmobiliarios.xlsx'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', type=str, default='requerimientos/data/requerimientos_inmobiliarios.xlsx',
                            help='Ruta al archivo Excel')
        parser.add_argument('--hoja', type=str, default=0,
                            help='Nombre o índice de la hoja a importar')
        parser.add_argument('--limite', type=int, default=0,
                            help='Límite de filas a procesar (0 para todas)')

    def handle(self, *args, **options):
        ruta = options['ruta']
        hoja = options['hoja']
        limite = options['limite']

        if not os.path.exists(ruta):
            self.stderr.write(self.style.ERROR(f'Archivo no encontrado: {ruta}'))
            return

        self.stdout.write(f'Leyendo archivo {ruta}...')
        try:
            df = pd.read_excel(ruta, sheet_name=hoja, header=0)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error al leer el Excel: {e}'))
            return

        self.stdout.write(f'Filas leídas: {len(df)}')
        self.stdout.write(f'Columnas encontradas: {list(df.columns)}')

        if limite > 0:
            df = df.head(limite)
            self.stdout.write(f'Procesando solo {limite} filas')

        creados = 0
        errores = 0

        # Mapeo de nombres de columna a campos del modelo
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

                # Mapear fuente - preservar los tres tipos de fuentes del Excel
                fuente_val_str = str(fuente_val).strip().upper()
                if 'RED INMOBILIARIA AREQUIPA' in fuente_val_str:
                    fuente = FuenteChoices.RED_INMOBILIARIA
                elif 'ÉXITO INMOBILIARIO' in fuente_val_str or 'EXITO INMOBILIARIO' in fuente_val_str:
                    fuente = FuenteChoices.EXITO
                elif 'INMOBILIARIAS UNIDAS' in fuente_val_str:
                    fuente = FuenteChoices.UNIDAS
                else:
                    fuente = FuenteChoices.OTRO

                # Parsear fecha
                fecha = None
                if not pd.isna(fecha_val):
                    try:
                        if isinstance(fecha_val, datetime):
                            fecha = fecha_val.date()
                        elif isinstance(fecha_val, pd.Timestamp):
                            fecha = fecha_val.date()
                        else:
                            # Intentar parsear formato dd/mm/yy
                            parts = str(fecha_val).split('/')
                            if len(parts) == 3:
                                day, month, year = map(int, parts)
                                if year < 100:
                                    year += 2000
                                fecha = datetime(year, month, day).date()
                    except:
                        pass

                # Parsear hora
                hora = None
                if not pd.isna(hora_val):
                    try:
                        if isinstance(hora_val, datetime):
                            hora = hora_val.time()
                        elif isinstance(hora_val, pd.Timestamp):
                            hora = hora_val.time()
                        else:
                            parts = str(hora_val).split(':')
                            if len(parts) >= 2:
                                hour = int(parts[0])
                                minute = int(parts[1])
                                from datetime import time
                                hora = time(hour, minute)
                    except:
                        pass

                # Mapear condición basada en Tipo Original
                condicion = CondicionChoices.NO_ESPECIFICADO
                tipo_original_str = str(tipo_original_val).lower()
                if 'compra' in tipo_original_str:
                    condicion = CondicionChoices.COMPRA
                elif 'alquiler' in tipo_original_str:
                    condicion = CondicionChoices.ALQUILER
                elif 'anticresis' in tipo_original_str:
                    condicion = CondicionChoices.COMPRA

                # Mapear tipo de propiedad
                tipo_propiedad = TipoPropiedadChoices.NO_ESPECIFICADO
                tipo_propiedad_str = str(tipo_propiedad_val).lower()
                if 'departamento' in tipo_propiedad_str:
                    tipo_propiedad = TipoPropiedadChoices.DEPARTAMENTO
                elif 'casa' in tipo_propiedad_str:
                    tipo_propiedad = TipoPropiedadChoices.CASA
                elif 'terreno' in tipo_propiedad_str:
                    tipo_propiedad = TipoPropiedadChoices.TERRENO
                elif 'local' in tipo_propiedad_str or 'comercial' in tipo_propiedad_str:
                    tipo_propiedad = TipoPropiedadChoices.LOCAL_COMERCIAL
                elif 'almacén' in tipo_propiedad_str or 'almacen' in tipo_propiedad_str:
                    tipo_propiedad = TipoPropiedadChoices.ALMACEN
                elif 'oficina' in tipo_propiedad_str:
                    tipo_propiedad = TipoPropiedadChoices.OFICINA

                # Mapear moneda
                moneda = MonedaChoices.NO_ESPECIFICADO
                moneda_str = str(moneda_val).upper()
                if 'USD' in moneda_str:
                    moneda = MonedaChoices.USD
                elif 'PEN' in moneda_str or 'SOL' in moneda_str:
                    moneda = MonedaChoices.PEN

                # Mapear forma de pago
                forma_pago = FormaPagoChoices.NO_ESPECIFICADO
                forma_pago_str = str(forma_pago_val).lower()
                if 'contado' in forma_pago_str:
                    forma_pago = FormaPagoChoices.CONTADO
                elif 'crédito' in forma_pago_str or 'credito' in forma_pago_str or 'hipotecario' in forma_pago_str:
                    forma_pago = FormaPagoChoices.FINANCIADO

                # Mapear ternarios
                def mapear_ternario(val):
                    if pd.isna(val):
                        return TernarioChoices.INDIFERENTE
                    val_str = str(val).lower()
                    if 'si' in val_str or 'sí' in val_str:
                        return TernarioChoices.SI
                    if 'no' in val_str:
                        return TernarioChoices.NO
                    return TernarioChoices.INDIFERENTE

                cochera = mapear_ternario(cochera_val)
                ascensor = mapear_ternario(ascensor_val)
                amueblado = mapear_ternario(amueblado_val)

                # Convertir números
                presupuesto_monto = None
                if not pd.isna(presupuesto_monto_val):
                    try:
                        presupuesto_monto = float(presupuesto_monto_val)
                    except:
                        pass

                habitaciones = None
                if not pd.isna(habitaciones_val):
                    try:
                        habitaciones = int(habitaciones_val)
                    except:
                        pass

                banos = None
                if not pd.isna(banos_val):
                    try:
                        banos = int(banos_val)
                    except:
                        pass

                area_m2 = None
                if not pd.isna(area_m2_val):
                    try:
                        area_m2 = int(area_m2_val)
                    except:
                        pass

                # Crear requerimiento
                req = Requerimiento(
                    fuente=fuente,
                    fecha=fecha,
                    hora=hora,
                    agente=str(agente_val)[:120],
                    tipo_original=str(tipo_original_val)[:80],
                    condicion=condicion,
                    tipo_propiedad=tipo_propiedad,
                    distritos=str(distritos_val)[:300],
                    presupuesto_monto=presupuesto_monto,
                    presupuesto_moneda=moneda,
                    presupuesto_forma_pago=forma_pago,
                    habitaciones=habitaciones,
                    banos=banos,
                    cochera=cochera,
                    ascensor=ascensor,
                    amueblado=amueblado,
                    area_m2=area_m2,
                    piso_preferencia=str(piso_preferencia_val)[:60],
                    caracteristicas_extra=str(caracteristicas_extra_val)[:300],
                    agente_telefono=str(agente_telefono_val)[:20],
                    requerimiento=str(requerimiento_val)[:5000],
                )
                req.save()
                creados += 1

                if creados % 50 == 0:
                    self.stdout.write(f'  Procesados {creados} registros...')

            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error en fila {idx}: {e}'))
                errores += 1

        self.stdout.write(self.style.SUCCESS(
            f'Importación completada: {creados} creados, {errores} errores'
        ))