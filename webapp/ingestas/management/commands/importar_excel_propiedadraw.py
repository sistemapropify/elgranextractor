"""
Comando de gestión para importar datos desde un archivo Excel a la tabla PropiedadRaw.
Asume que las columnas del Excel coinciden con los campos del modelo PropiedadRaw.
"""

import os
import sys
import traceback
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ingestas.models import PropiedadRaw
from decimal import Decimal, InvalidOperation


class Command(BaseCommand):
    help = 'Importa registros desde un archivo Excel a la tabla PropiedadRaw.'

    def add_arguments(self, parser):
        parser.add_argument(
            'archivo',
            type=str,
            help='Ruta al archivo Excel (.xlsx o .xls)'
        )
        parser.add_argument(
            '--hoja',
            type=str,
            default=0,
            help='Nombre o índice de la hoja a leer (por defecto: primera hoja)'
        )
        parser.add_argument(
            '--fuente',
            type=str,
            default='excel_importado',
            help='Valor para el campo fuente_excel (si no existe columna fuente_excel)'
        )
        parser.add_argument(
            '--skip-errors',
            action='store_true',
            help='Continuar importación aunque algunas filas fallen'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular importación sin guardar en la base de datos'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Límite de filas a importar (0 para todas)'
        )

    def handle(self, *args, **options):
        archivo = options['archivo']
        hoja = options['hoja']
        fuente = options['fuente']
        skip_errors = options['skip_errors']
        dry_run = options['dry_run']
        limit = options['limit']

        if not os.path.exists(archivo):
            raise CommandError(f'El archivo "{archivo}" no existe.')

        # Intentar importar pandas
        try:
            import pandas as pd
        except ImportError:
            self.stderr.write(
                'Error: pandas no está instalado. Instálalo con: pip install pandas openpyxl'
            )
            sys.exit(1)

        self.stdout.write(f'Leyendo archivo: {archivo}')
        try:
            # Leer Excel
            df = pd.read_excel(archivo, sheet_name=hoja, dtype=str)  # Leer todo como string para manejar nulos
        except Exception as e:
            raise CommandError(f'Error al leer el archivo Excel: {e}')

        # Limitar filas si se especifica
        if limit > 0:
            df = df.head(limit)

        total_filas = len(df)
        self.stdout.write(f'Total de filas en Excel: {total_filas}')

        # Mapeo de columnas del Excel a campos del modelo
        # Se espera que los nombres de columna coincidan con los nombres de campo del modelo
        # pero se pueden normalizar (eliminar espacios, minúsculas)
        columnas_excel = df.columns.tolist()
        self.stdout.write(f'Columnas encontradas: {", ".join(columnas_excel)}')

        # Campos del modelo PropiedadRaw
        campos_modelo = [f.name for f in PropiedadRaw._meta.get_fields()]
        self.stdout.write(f'Campos del modelo: {", ".join(campos_modelo)}')

        # Crear mapeo: columna -> campo (insensible a mayúsculas y espacios)
        mapeo = {}
        # Mapeo manual específico para el Excel de Remax
        mapeo_manual = {
            'fuente-excel': 'fuente_excel',
            'identificador-externo': 'identificador_externo',
            'Tipo de Propiedad': 'tipo_propiedad',
            'Subtipo de propiedad': 'subtipo_propiedad',
            'URL de la Propiedad': 'url_propiedad',
            'Precio (USD)': 'precio_usd',
            'Área de Terreno (m²)': 'area_terreno',
            'Área Construida (m²)': 'area_construida',
            'Número de Pisos': 'numero_pisos',
            'Número de Habitaciones': 'numero_habitaciones',
            'Número de Baños': 'numero_banos',
            'Número de Cocheras': 'numero_cocheras',
            'Imágenes de la Propiedad': 'imagenes_propiedad',
            'ID de la Propiedad': 'id_propiedad',
            'Fecha de Publicación': 'fecha_publicacion',
            'Descripción Detallada': 'descripcion',
            'Antigüedad': 'antiguedad',
            'Servicio de Agua': 'servicio_agua',
            'Energía Eléctrica': 'energia_electrica',
            'Servicio de Drenaje': 'servicio_drenaje',
            'Servicio de Gas': 'servicio_gas',
            'Email del Agente': 'email_agente',
            'Teléfono del Agente': 'telefono_agente',
            'Oficina RE/MAX': 'oficina_remax',
        }
        # También mapear variantes con caracteres especiales
        mapeo_manual_variantes = {
            'Tipo de propiedad': 'tipo_propiedad',
            'Subtipo de propiedad': 'subtipo_propiedad',
            '�rea de Terreno (m�)': 'area_terreno',
            '�rea Construida (m�)': 'area_construida',
            'N�mero de Pisos': 'numero_pisos',
            'N�mero de Habitaciones': 'numero_habitaciones',
            'N�mero de Ba�os': 'numero_banos',
            'N�mero de Cocheras': 'numero_cocheras',
            'Im�genes de la Propiedad': 'imagenes_propiedad',
            'ID de la Propiedad': 'id_propiedad',
            'Fecha de Publicaci�n': 'fecha_publicacion',
            'Descripci�n Detallada': 'descripcion',
            'Antig�edad': 'antiguedad',
            'Servicio de Agua': 'servicio_agua',
            'Energ�a El�ctrica': 'energia_electrica',
            'Servicio de Drenaje': 'servicio_drenaje',
            'Servicio de Gas': 'servicio_gas',
            'Email del Agente': 'email_agente',
            'Tel�fono del Agente': 'telefono_agente',
            'Oficina RE/MAX': 'oficina_remax',
        }
        
        for col in columnas_excel:
            col_str = str(col)
            # Primero intentar mapeo manual
            if col_str in mapeo_manual:
                mapeo[col] = mapeo_manual[col_str]
                continue
            if col_str in mapeo_manual_variantes:
                mapeo[col] = mapeo_manual_variantes[col_str]
                continue
            # Limpiar nombre de columna para comparación
            col_clean = col_str.strip().lower().replace(' ', '_').replace('�', '').replace('(', '').replace(')', '').replace('m�', 'm2')
            for campo in campos_modelo:
                if campo.lower() == col_clean:
                    mapeo[col] = campo
                    break
            else:
                # Si no coincide, se puede ignorar o mapear manualmente
                # Por ahora, ignorar columnas no reconocidas
                self.stdout.write(
                    self.style.WARNING(f'Columna "{col}" no coincide con ningún campo del modelo. Se ignorará.')
                )

        self.stdout.write(f'Mapeo automático: {mapeo}')

        # Verificar que al menos haya algunas columnas mapeadas
        if not mapeo:
            raise CommandError('No se pudo mapear ninguna columna del Excel a campos del modelo.')

        # Contadores
        exitos = 0
        errores = 0
        fila_num = 0

        # Usar transacción atómica a menos que sea dry-run
        if dry_run:
            self.stdout.write(self.style.NOTICE('--- MODO SIMULACIÓN (dry-run) ---'))

        with transaction.atomic():
            for _, fila in df.iterrows():
                fila_num += 1
                try:
                    datos = {}
                    # Procesar cada columna mapeada
                    for col, campo in mapeo.items():
                        valor = fila[col]
                        # Si es NaN (float) o None, asignar None
                        if pd.isna(valor):
                            datos[campo] = None
                            continue

                        # Convertir según el tipo de campo del modelo
                        field = PropiedadRaw._meta.get_field(campo)
                        if field.get_internal_type() == 'DecimalField':
                            # Intentar convertir a Decimal
                            try:
                                # Eliminar caracteres no numéricos como moneda, comas, etc.
                                if isinstance(valor, str):
                                    valor = valor.replace('$', '').replace(',', '').strip()
                                datos[campo] = Decimal(str(valor))
                            except (InvalidOperation, ValueError) as e:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Fila {fila_num}: valor "{valor}" no válido para {campo}. Se guardará como None.'
                                    )
                                )
                                datos[campo] = None
                        elif field.get_internal_type() == 'IntegerField':
                            try:
                                datos[campo] = int(float(valor))
                            except (ValueError, TypeError):
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Fila {fila_num}: valor "{valor}" no válido para {campo}. Se guardará como None.'
                                    )
                                )
                                datos[campo] = None
                        elif field.get_internal_type() == 'DateField':
                            try:
                                # Si es Timestamp de pandas, convertirlo a date
                                if hasattr(valor, 'date'):
                                    datos[campo] = valor.date()
                                elif isinstance(valor, str):
                                    # Limpiar caracteres extraños (como �)
                                    valor_limpio = valor.strip().replace('�', '').replace('"', '').replace("'", '')
                                    # Intentar parsear como fecha
                                    from datetime import datetime
                                    # Puede estar en formato YYYY-MM-DD HH:MM:SS
                                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                                        try:
                                            dt = datetime.strptime(valor_limpio, fmt)
                                            datos[campo] = dt.date()
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        raise ValueError(f'Formato de fecha no reconocido: {valor_limpio}')
                                else:
                                    # Asumir que es datetime.date o similar
                                    datos[campo] = valor
                            except Exception as e:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Fila {fila_num}: valor "{valor}" no válido para {campo} ({e}). Se guardará como None.'
                                    )
                                )
                                datos[campo] = None
                        elif field.get_internal_type() == 'TextField':
                            datos[campo] = str(valor)
                        else:
                            # Para CharField, URLField, etc., convertir a string
                            datos[campo] = str(valor) if not pd.isna(valor) else None

                    # Si no se mapeó fuente_excel, usar el valor por defecto
                    if 'fuente_excel' not in datos:
                        datos['fuente_excel'] = fuente

                    # Crear instancia del modelo
                    instancia = PropiedadRaw(**datos)

                    if not dry_run:
                        instancia.save()
                    exitos += 1

                    if fila_num % 100 == 0:
                        self.stdout.write(f'Procesadas {fila_num} filas...')

                except Exception as e:
                    errores += 1
                    error_msg = f'Fila {fila_num}: Error al procesar - {e}'
                    self.stdout.write(self.style.ERROR(error_msg))
                    self.stdout.write(traceback.format_exc())
                    if not skip_errors:
                        raise CommandError(f'Importación abortada debido a error en fila {fila_num}.')
                    # Continuar si skip_errors está activado

            if dry_run:
                # Revertir transacción (no se guardó nada)
                transaction.set_rollback(True)

        # Resumen
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('IMPORTACIÓN COMPLETADA'))
        self.stdout.write(self.style.SUCCESS(f'Total filas procesadas: {fila_num}'))
        self.stdout.write(self.style.SUCCESS(f'Registros exitosos: {exitos}'))
        self.stdout.write(self.style.ERROR(f'Errores: {errores}'))
        if dry_run:
            self.stdout.write(self.style.NOTICE('(Modo simulación: ningún registro guardado)'))