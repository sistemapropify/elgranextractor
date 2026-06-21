"""
Management command para borrar todos los registros de requerimientos
extraidos desde WhatsApp, incluyendo logs y archivos asociados.

Elimina en orden (respetando FK):
1. LogEntry (depende de ExtractorLog)
2. Requerimiento (tiene FK a ExtractorLog, pero con SET_NULL)
3. ExtractorLog
4. ArchivoExtraccionWhatsApp
5. WhatsappGroupSession (opcional, con --incluir-grupos)

Uso:
    python manage.py borrar_requerimientos_whatsapp
    python manage.py borrar_requerimientos_whatsapp --incluir-grupos
    python manage.py borrar_requerimientos_whatsapp --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from requerimientos.models import Requerimiento
from whatsapp_extractor.models import (
    ExtractorLog,
    LogEntry,
    ArchivoExtraccionWhatsApp,
    WhatsappGroupSession,
)


class Command(BaseCommand):
    help = 'Borra todos los requerimientos extraidos desde WhatsApp y sus logs asociados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--incluir-grupos',
            action='store_true',
            help='Incluye tambien las configuraciones de grupos WhatsApp',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra lo que se borraria sin ejecutar',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ejecuta sin pedir confirmacion (para uso no interactivo)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        incluir_grupos = options['incluir_grupos']

        # Contar registros actuales
        total_requerimientos = Requerimiento.objects.count()
        total_logs = ExtractorLog.objects.count()
        total_log_entries = LogEntry.objects.count()
        total_archivos = ArchivoExtraccionWhatsApp.objects.count()
        total_grupos = WhatsappGroupSession.objects.count()

        self.stdout.write(self.style.WARNING('--- RESUMEN DE REGISTROS A BORRAR ---'))
        self.stdout.write(f'  Requerimientos:              {total_requerimientos}')
        self.stdout.write(f'  Logs de extraccion:          {total_logs}')
        self.stdout.write(f'  Entradas de log detallado:   {total_log_entries}')
        self.stdout.write(f'  Archivos de extraccion:      {total_archivos}')
        self.stdout.write(f'  Grupos WhatsApp:             {total_grupos} {"(se incluiran)" if incluir_grupos else "(NO se borraran)"}')
        self.stdout.write('')

        if total_requerimientos == 0 and total_logs == 0 and total_archivos == 0:
            self.stdout.write(self.style.SUCCESS('OK: No hay registros que borrar.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: no se borro nada.'))
            return

        # Confirmacion
        if not options['force']:
            self.stdout.write(self.style.WARNING('ATENCION: Estas seguro de borrar TODOS estos registros?'))
            confirm = input('  Escribe "si" para confirmar: ')
            if confirm.lower() not in ('si', 's'):
                self.stdout.write(self.style.WARNING('Operacion cancelada.'))
                return

        # Ejecutar borrado en transaccion
        with transaction.atomic():
            # 1. LogEntry (depende de ExtractorLog via CASCADE)
            deleted_entries = LogEntry.objects.all().delete()[0]
            self.stdout.write(f'  OK: Entradas de log borradas: {deleted_entries}')

            # 2. Requerimiento (tiene FK a ExtractorLog con SET_NULL, se borra directo)
            deleted_reqs = Requerimiento.objects.all().delete()[0]
            self.stdout.write(f'  OK: Requerimientos borrados: {deleted_reqs}')

            # 3. ExtractorLog
            deleted_logs = ExtractorLog.objects.all().delete()[0]
            self.stdout.write(f'  OK: Logs de extraccion borrados: {deleted_logs}')

            # 4. ArchivoExtraccionWhatsApp
            deleted_archivos = ArchivoExtraccionWhatsApp.objects.all().delete()[0]
            self.stdout.write(f'  OK: Archivos de extraccion borrados: {deleted_archivos}')

            # 5. WhatsappGroupSession (opcional)
            if incluir_grupos:
                deleted_grupos = WhatsappGroupSession.objects.all().delete()[0]
                self.stdout.write(f'  OK: Grupos WhatsApp borrados: {deleted_grupos}')

        self.stdout.write(self.style.SUCCESS('\nTodos los registros han sido borrados exitosamente.'))
