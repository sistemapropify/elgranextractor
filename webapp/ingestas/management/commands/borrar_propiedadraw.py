"""
Comando de gestión para borrar toda la estructura de la tabla PropiedadRaw.
Permite eliminar registros de PropiedadRaw y tablas relacionadas para revalidar y reingresar campos.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.apps import apps
from django.conf import settings
import sys

class Command(BaseCommand):
    help = 'Borra todos los registros de la tabla PropiedadRaw y opcionalmente tablas relacionadas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tablas-relacionadas',
            action='store_true',
            dest='tablas_relacionadas',
            help='Incluye borrado de CampoDinamico, MapeoFuente y MigracionPendiente',
        )
        parser.add_argument(
            '--solo-datos',
            action='store_true',
            dest='solo_datos',
            help='Borra solo los datos (DELETE) sin afectar la estructura de la tabla (por defecto)',
        )
        parser.add_argument(
            '--estructura',
            action='store_true',
            dest='estructura',
            help='Borra y recrea la tabla (DROP y CREATE) - PELIGROSO: requiere migraciones',
        )
        parser.add_argument(
            '--confirmar',
            action='store_true',
            dest='confirmar',
            help='Confirmar automáticamente sin preguntar',
        )
        parser.add_argument(
            '--listar',
            action='store_true',
            dest='listar',
            help='Listar las tablas que serían afectadas sin ejecutar borrado',
        )

    def handle(self, *args, **options):
        tablas_relacionadas = options['tablas_relacionadas']
        solo_datos = options['solo_datos']
        estructura = options['estructura']
        confirmar = options['confirmar']
        listar = options['listar']

        # Determinar modelo PropiedadRaw
        try:
            PropiedadRaw = apps.get_model('ingestas', 'PropiedadRaw')
        except LookupError:
            raise CommandError('No se encontró el modelo PropiedadRaw en la app ingestas.')

        # Tablas a borrar
        tablas = ['ingestas_propiedadraw']
        if tablas_relacionadas:
            tablas.extend([
                'ingestas_campodinamico',
                'ingestas_mapeofuente',
                'ingestas_migracionpendiente',
            ])

        if listar:
            self.stdout.write(self.style.WARNING('Tablas que serían afectadas:'))
            for tabla in tablas:
                self.stdout.write(f'  - {tabla}')
            return

        # Advertencia
        if estructura:
            self.stdout.write(self.style.ERROR('ADVERTENCIA: La opción --estructura borrará y recreará la tabla.'))
            self.stdout.write(self.style.ERROR('Esto puede causar pérdida de datos y requerir migraciones.'))
            if not confirmar:
                respuesta = input('¿Está seguro? (escriba "SI" para continuar): ')
                if respuesta.strip().upper() != 'SI':
                    self.stdout.write(self.style.WARNING('Operación cancelada.'))
                    return
        else:
            self.stdout.write(self.style.WARNING(f'Se borrarán TODOS los registros de {len(tablas)} tabla(s).'))
            self.stdout.write(self.style.WARNING('Esta acción no se puede deshacer.'))
            if not confirmar:
                respuesta = input('¿Continuar? (s/n): ')
                if respuesta.strip().lower() != 's':
                    self.stdout.write(self.style.WARNING('Operación cancelada.'))
                    return

        # Ejecutar borrado
        with transaction.atomic():
            if estructura:
                self._recrear_tabla(PropiedadRaw, tablas)
            else:
                self._borrar_datos(tablas, solo_datos)

        self.stdout.write(self.style.SUCCESS('Operación completada exitosamente.'))

    def _borrar_datos(self, tablas, solo_datos):
        """Elimina todos los registros de las tablas usando DELETE o TRUNCATE."""
        with connection.cursor() as cursor:
            for tabla in tablas:
                if solo_datos:
                    cursor.execute(f'DELETE FROM {tabla}')
                    self.stdout.write(f'DELETE FROM {tabla} - {cursor.rowcount} filas eliminadas.')
                else:
                    # TRUNCATE es más rápido y reinicia los autoincrementos
                    try:
                        cursor.execute(f'TRUNCATE TABLE {tabla} RESTART IDENTITY CASCADE')
                        self.stdout.write(f'TRUNCATE TABLE {tabla} (con RESTART IDENTITY CASCADE).')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'No se pudo TRUNCATE {tabla}: {e}. Usando DELETE.'))
                        cursor.execute(f'DELETE FROM {tabla}')
                        self.stdout.write(f'DELETE FROM {tabla} - {cursor.rowcount} filas eliminadas.')

    def _recrear_tabla(self, modelo, tablas):
        """Borra y recrea la tabla usando migraciones inversas."""
        self.stdout.write(self.style.WARNING('La recreación de tablas no está implementada completamente.'))
        self.stdout.write(self.style.WARNING('Use `python manage.py migrate ingestas zero` y luego `python manage.py migrate ingestas`.'))
        raise CommandError('La opción --estructura requiere implementación adicional.')