import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from requerimientos.models import Requerimiento, FuenteChoices
import os
import sys


class Command(BaseCommand):
    help = 'Importa requerimientos desde un archivo Excel (requerimientos_completo.xlsx)'

    def add_arguments(self, parser):
        parser.add_argument('--ruta', type=str, default='requerimientos/data/requerimientos_completo.xlsx',
                            help='Ruta al archivo Excel')
        parser.add_argument('--hoja', type=str, default='Todos los Registros',
                            help='Nombre de la hoja a importar')
        parser.add_argument('--fila-inicio', type=int, default=2,
                            help='Fila donde empiezan los datos (encabezados en fila anterior)')
        parser.add_argument('--limite', type=int, default=0,
                            help='Límite de filas a procesar (0 para todas)')

    def handle(self, *args, **options):
        ruta = options['ruta']
        hoja = options['hoja']
        fila_inicio = options['fila_inicio']
        limite = options['limite']

        if not os.path.exists(ruta):
            self.stderr.write(self.style.ERROR(f'Archivo no encontrado: {ruta}'))
            return

        self.stdout.write(f'Leyendo archivo {ruta}...')
        try:
            df = pd.read_excel(ruta, sheet_name=hoja, header=fila_inicio-1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error al leer el Excel: {e}'))
            return

        self.stdout.write(f'Filas leídas: {len(df)}')
        # Mostrar columnas sin caracteres problemáticos
        columnas_safe = []
        for col in df.columns:
            try:
                str(col)
                columnas_safe.append(col)
            except:
                columnas_safe.append(repr(col))
        self.stdout.write(f'Columnas encontradas: {len(df.columns)}')
        for i, col in enumerate(columnas_safe[:20]):
            self.stdout.write(f'  {i+1}. {col}')
        if len(df.columns) > 20:
            self.stdout.write(f'  ... y {len(df.columns) - 20} más')

        # Mapeo de índices de columna Excel a campos del modelo
        # Basado en la estructura del Excel: columna 0=ID, 1=fuente, 2=fecha, 3=hora, 4=agente, etc.
        mapeo_indices = {
            'fuente': 1,           # Columna 1: 'wattsapp inmobiliarias unidas'
            'fecha': 2,            # Columna 2: '15/12/2025'
            'hora': 3,             # Columna 3: '11:10:32 a.m.'
            'agente': 4,           # Columna 4: 'Marco Valenzuela Agente Inmobiliario'
            'tipo_original': 5,    # Columna 5: 'PROPIEDAD VENTA'
            'condicion': 6,        # Columna 6: 'no especificado'
            'tipo_propiedad': 7,   # Columna 7: 'casa'
            'distritos': 8,        # Columna 8: 'Cayma Baja'
            'presupuesto_monto': 9, # Columna 9: 780000
            'presupuesto_moneda': 10, # Columna 10: 'USD'
            'presupuesto_forma_pago': 11, # Columna 11: 'no especificado.1'
            'habitaciones': 12,    # Columna 12: 4
            'banos': 13,           # Columna 13: '1.1'
            'cochera': 14,         # Columna 14: 'si'
            'ascensor': 15,        # Columna 15: 'indiferente'
            'amueblado': 16,       # Columna 16: 'indiferente.1'
            'area_m2': 17,         # Columna 17: 207
            'piso_preferencia': 18, # Columna 18: 'Piso Preferencia'
            'caracteristicas_extra': 19, # Columna 19: 'Caracteristicas Extra'
            'agente_telefono': 20, # Columna 20: 'Tel Agente'
            'requerimiento': 21,   # Columna 21: 'Requerimiento' (descripción/mensaje en crudo)
        }

        def convertir_valor(campo, valor):
            if pd.isna(valor):
                return None
            if isinstance(valor, str):
                valor = valor.strip()
                if valor == '':
                    return None
            if campo in ('habitaciones', 'piso_preferencia'):
                if valor is None:
                    return None
                try:
                    return int(float(valor))
                except:
                    return None
            if campo == 'banos':
                if valor is None:
                    return None
                try:
                    # Manejar valores como '1.1' (1 baño completo + 1 medio baño)
                    if isinstance(valor, str):
                        # Intentar convertir a float primero
                        return float(valor)
                    else:
                        return float(valor)
                except:
                    return None
            # Campos con TernarioChoices (si, no, indiferente)
            if campo in ('cochera', 'ascensor', 'amueblado'):
                if valor is None:
                    return 'indiferente'  # Valor por defecto
                if isinstance(valor, str):
                    valor = valor.strip().lower()
                    # Limpiar '.1' de 'indiferente.1'
                    if valor.endswith('.1'):
                        valor = valor[:-2]
                    if valor in ('si', 'sí', 'yes', 'true', '1'):
                        return 'si'
                    elif valor in ('no', 'false', '0'):
                        return 'no'
                    elif valor in ('indiferente', 'indiferent', 'cualquiera'):
                        return 'indiferente'
                    else:
                        return 'indiferente'  # Valor por defecto
                elif isinstance(valor, (int, float)):
                    if valor == 0:
                        return 'no'
                    elif valor == 1:
                        return 'si'
                    else:
                        return 'indiferente'
                else:
                    return 'indiferente'
            if campo == 'area_m2':
                if valor is None:
                    return None
                try:
                    return float(valor)
                except:
                    return None
            if campo == 'presupuesto_monto':
                if valor is None:
                    return None
                try:
                    return float(valor)
                except:
                    return None
            if campo == 'fecha':
                if isinstance(valor, pd.Timestamp):
                    return valor.date()
                elif isinstance(valor, str):
                    # Limpiar caracteres extraños y convertir formato DD/MM/YYYY
                    valor = valor.strip()
                    # Remover caracteres no ASCII
                    import re
                    valor = re.sub(r'[^\d/]', '', valor)
                    try:
                        from datetime import datetime
                        # Intentar parsear DD/MM/YYYY
                        return datetime.strptime(valor, '%d/%m/%Y').date()
                    except:
                        try:
                            # Intentar parsear YYYY-MM-DD
                            return datetime.strptime(valor, '%Y-%m-%d').date()
                        except:
                            return None
            if campo == 'hora':
                if isinstance(valor, pd.Timestamp):
                    return valor.time()
                elif isinstance(valor, str):
                    valor = valor.strip()
                    # Remover caracteres no ASCII y 'a.m.'/'p.m.'
                    import re
                    valor = re.sub(r'[^\d:]', '', valor)
                    try:
                        from datetime import datetime
                        # Intentar parsear HH:MM:SS
                        return datetime.strptime(valor, '%H:%M:%S').time()
                    except:
                        try:
                            # Intentar parsear HH:MM
                            return datetime.strptime(valor, '%H:%M').time()
                        except:
                            return None
            # Normalizar fuente a choices
            if campo == 'fuente' and isinstance(valor, str):
                valor = valor.strip().lower()
                if 'inmobiliarias unidas' in valor:
                    return 'inmobiliarias_unidas'
                elif 'éxito' in valor or 'exito' in valor:
                    return 'exito_inmobiliario'
                else:
                    return 'otro'
            # Truncar valores de texto que excedan la longitud máxima del campo
            if isinstance(valor, str):
                # Longitudes máximas por campo (basado en el modelo)
                max_lengths = {
                    'tipo_original': 80,
                    'condicion': 20,
                    'tipo_propiedad': 20,
                    'distritos': 300,
                    'presupuesto_moneda': 20,
                    'presupuesto_forma_pago': 20,
                    'piso_preferencia': 60,
                    'caracteristicas_extra': 300,
                    'agente': 200,
                    'agente_telefono': 20,
                    'requerimiento': 500,
                }
                if campo in max_lengths:
                    max_len = max_lengths[campo]
                    if len(valor) > max_len:
                        valor = valor[:max_len]
            return valor

        creados = 0
        errores = []
        if limite > 0:
            df = df.head(limite)

        with transaction.atomic():
            for idx, row in df.iterrows():
                # Usar savepoint para manejar errores por fila sin romper toda la transacción
                sid = transaction.savepoint()
                try:
                    datos = {}
                    for campo_modelo, col_idx in mapeo_indices.items():
                        if col_idx < len(df.columns):
                            valor = row.iloc[col_idx]
                            datos[campo_modelo] = convertir_valor(campo_modelo, valor)
                        else:
                            datos[campo_modelo] = None

                    # NOTA: es_urgente es una propiedad (@property), no un campo de base de datos
                    # No lo incluimos en el diccionario de datos

                    # Asegurar que fuente no sea None
                    if datos.get('fuente') is None:
                        datos['fuente'] = 'otro'

                    # Asegurar que agente no sea None (campo requerido)
                    if datos.get('agente') is None:
                        datos['agente'] = 'Desconocido'
                    
                    # Asegurar que distritos no sea None (campo con blank=True pero DB puede requerir NOT NULL)
                    if datos.get('distritos') is None:
                        datos['distritos'] = ''

                    # Asegurar que requerimiento no sea None (campo obligatorio)
                    if datos.get('requerimiento') is None:
                        datos['requerimiento'] = ''

                    # Asegurar que agente_telefono no sea None (blank=True)
                    if datos.get('agente_telefono') is None:
                        datos['agente_telefono'] = ''

                    # Asegurar que piso_preferencia no sea None (blank=True)
                    if datos.get('piso_preferencia') is None:
                        datos['piso_preferencia'] = ''

                    # Asegurar que caracteristicas_extra no sea None (blank=True)
                    if datos.get('caracteristicas_extra') is None:
                        datos['caracteristicas_extra'] = ''

                    # Crear requerimiento
                    Requerimiento.objects.create(**datos)
                    creados += 1
                    if creados % 100 == 0:
                        self.stdout.write(f'  {creados} registros creados...')
                    # Confirmar savepoint si todo va bien
                    transaction.savepoint_commit(sid)
                except Exception as e:
                    # Revertir savepoint para esta fila
                    transaction.savepoint_rollback(sid)
                    errores.append(f"Fila {idx + fila_inicio + 1}: {str(e)}")
                    if len(errores) <= 10:
                        self.stderr.write(self.style.ERROR(f'Fila {idx + fila_inicio + 1}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Importación completada. {creados} requerimientos creados.'))
        if errores:
            self.stdout.write(self.style.WARNING(f'{len(errores)} errores encontrados.'))
            for err in errores[:10]:
                self.stdout.write(self.style.WARNING(f'  {err}'))
            if len(errores) > 10:
                self.stdout.write(self.style.WARNING(f'  ... y {len(errores) - 10} más.'))