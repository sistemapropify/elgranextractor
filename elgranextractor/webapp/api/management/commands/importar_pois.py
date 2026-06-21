"""
Comando de management para importar Puntos de Interés desde un archivo CSV.

Uso:
    python manage.py importar_pois archivo.csv
    python manage.py importar_pois archivo.csv --crear-capas

Formato CSV esperado:
    nombre,slug_categoria,latitud,longitud,direccion,descripcion,telefono,sitio_web
    "Clínica Arequipa",hospital,-16.3988,-71.5375,"Av. Ejército 205","Clínica privada","054-123456","https://ejemplo.com"

Si la categoría (slug_categoria) no existe y se usa --crear-capas, se crea automáticamente.
"""
import csv
import sys
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import CategoriaPOI, PointOfInterest


class Command(BaseCommand):
    help = 'Importa Puntos de Interés desde un archivo CSV'

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al archivo CSV')
        parser.add_argument(
            '--crear-capas',
            action='store_true',
            help='Crear capas automáticamente si no existen',
        )
        parser.add_argument(
            '--delimiter',
            type=str,
            default=',',
            help='Delimitador del CSV (default: ,)',
        )
        parser.add_argument(
            '--encoding',
            type=str,
            default='utf-8',
            help='Encoding del archivo (default: utf-8)',
        )

    def handle(self, *args, **options):
        archivo = options['archivo']
        crear_capas = options['crear_capas']
        delimiter = options['delimiter']
        encoding = options['encoding']

        self.stdout.write(f"[IMPORT] Leyendo archivo: {archivo}")
        self.stdout.write(f"  Delimitador: '{delimiter}'")
        self.stdout.write(f"  Encoding: {encoding}")
        self.stdout.write(f"  Crear capas automaticas: {'SI' if crear_capas else 'NO'}")

        try:
            with open(archivo, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                filas = list(reader)
        except FileNotFoundError:
            raise CommandError(f"Archivo no encontrado: {archivo}")
        except Exception as e:
            raise CommandError(f"Error al leer el archivo: {e}")

        if not filas:
            self.stdout.write(self.style.WARNING("[WARN] El archivo CSV esta vacio"))
            return

        # Validar columnas requeridas
        columnas = filas[0].keys()
        columnas_requeridas = {'nombre', 'slug_categoria', 'latitud', 'longitud'}
        columnas_faltantes = columnas_requeridas - set(columnas)
        if columnas_faltantes:
            raise CommandError(
                f"Columnas requeridas faltantes: {', '.join(sorted(columnas_faltantes))}. "
                f"Columnas encontradas: {', '.join(columnas)}"
            )

        self.stdout.write(f"   Filas a procesar: {len(filas)}")
        self.stdout.write("")

        # Procesar
        creados = 0
        actualizados = 0
        errores = 0
        capas_creadas = set()

        with transaction.atomic():
            for i, fila in enumerate(filas, start=2):  # start=2 por header
                try:
                    self._procesar_fila(
                        fila, crear_capas, capas_creadas,
                        lambda: self._actualizar_contadores(creados, actualizados, errores)
                    )
                except Exception as e:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(f"  [ERROR] Linea {i}: {e}")
                    )

        # Resumen
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[OK] Importacion completada"))
        self.stdout.write(f"   Creados: {creados}")
        self.stdout.write(f"   Actualizados: {actualizados}")
        self.stdout.write(f"   Errores: {errores}")
        if capas_creadas:
            self.stdout.write(f"   Capas creadas: {', '.join(sorted(capas_creadas))}")

    def _procesar_fila(self, fila, crear_capas, capas_creadas, actualizar_callback):
        nombre = fila.get('nombre', '').strip()
        slug_categoria = fila.get('slug_categoria', '').strip().lower()
        latitud_str = fila.get('latitud', '').strip()
        longitud_str = fila.get('longitud', '').strip()

        if not nombre:
            raise ValueError("El campo 'nombre' es obligatorio")
        if not slug_categoria:
            raise ValueError("El campo 'slug_categoria' es obligatorio")
        if not latitud_str or not longitud_str:
            raise ValueError("Los campos 'latitud' y 'longitud' son obligatorios")

        # Validar coordenadas
        try:
            latitud = Decimal(latitud_str)
            longitud = Decimal(longitud_str)
        except InvalidOperation:
            raise ValueError(f"Coordenadas inválidas: lat={latitud_str}, lng={longitud_str}")

        if not (-90 <= latitud <= 90):
            raise ValueError(f"Latitud fuera de rango: {latitud}")
        if not (-180 <= longitud <= 180):
            raise ValueError(f"Longitud fuera de rango: {longitud}")

        # Obtener o crear categoría
        try:
            categoria = CategoriaPOI.objects.get(slug=slug_categoria)
        except CategoriaPOI.DoesNotExist:
            if not crear_capas:
                raise ValueError(
                    f"Categoría '{slug_categoria}' no existe. "
                    f"Usa --crear-capas para crearla automáticamente, "
                    f"o créala desde el admin primero."
                )
            # Crear categoría automáticamente
            nombre_categoria = fila.get('nombre_categoria', slug_categoria.replace('_', ' ').title())
            categoria = CategoriaPOI.objects.create(
                nombre=nombre_categoria,
                slug=slug_categoria,
                is_active=True,
            )
            capas_creadas.add(slug_categoria)
            self.stdout.write(f"  [NUEVA] Capa creada: '{slug_categoria}' -> '{nombre_categoria}'")

        # Campos opcionales
        direccion = fila.get('direccion', '')
        descripcion = fila.get('descripcion', '')
        telefono = fila.get('telefono', '')
        sitio_web = fila.get('sitio_web', '')

        # Crear o actualizar POI
        poi, created = PointOfInterest.objects.update_or_create(
            nombre=nombre,
            categoria=categoria,
            latitud=latitud,
            longitud=longitud,
            defaults={
                'direccion': direccion,
                'descripcion': descripcion,
                'telefono': telefono,
                'sitio_web': sitio_web,
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(f"  [OK] Creado: {poi}")
        else:
            self.stdout.write(f"  [ACT] Actualizado: {poi}")
