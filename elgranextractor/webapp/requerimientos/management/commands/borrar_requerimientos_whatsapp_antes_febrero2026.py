"""
Management command para borrar requerimientos extraidos desde WhatsApp
que tengan fecha ANTERIOR a febrero 2026.

Esto NO borra los ExtractorLog, LogEntry, ArchivoExtraccionWhatsApp ni grupos.
Solo los registros Requerimiento que cumplen:
  - extractor_log IS NOT NULL (vinieron del extractor WhatsApp)
  - fecha < 2026-02-01

Uso:
    python manage.py borrar_requerimientos_whatsapp_antes_febrero2026
    python manage.py borrar_requerimientos_whatsapp_antes_febrero2026 --dry-run
    python manage.py borrar_requerimientos_whatsapp_antes_febrero2026 --force
"""

from datetime import date
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from requerimientos.models import Requerimiento


class Command(BaseCommand):
    help = 'Borra requerimientos WhatsApp con fecha anterior a febrero 2026'

    FECHA_LIMITE = date(2026, 2, 1)

    def add_arguments(self, parser):
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
        force = options['force']

        # --- 1. Consultar los registros a borrar ---
        qs = Requerimiento.objects.filter(
            extractor_log__isnull=False,
            fecha__lt=self.FECHA_LIMITE,
        )

        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                'OK: No hay requerimientos WhatsApp antes de febrero 2026.'
            ))
            return

        # --- 2. Estadisticas por mes ---
        fechas = qs.values_list('fecha', flat=True)
        contador_meses = Counter()
        for f in fechas:
            if f:
                clave = f.strftime('%Y-%m')
                contador_meses[clave] += 1

        self.stdout.write(self.style.WARNING(
            '--- REQUERIMIENTOS WHATSAPP A BORRAR (antes de febrero 2026) ---'
        ))
        self.stdout.write(f'  Total: {total}')
        self.stdout.write('')
        self.stdout.write('  Distribucion por mes:')
        for mes in sorted(contador_meses.keys()):
            self.stdout.write(f'    {mes}: {contador_meses[mes]}')
        self.stdout.write('')

        # Rango de fechas
        primera = qs.earliest('fecha').fecha if qs.exists() else 'N/A'
        ultima = qs.latest('fecha').fecha if qs.exists() else 'N/A'
        self.stdout.write(f'  Rango: {primera} -> {ultima}')

        # Total general de whatsapp
        total_whatsapp = Requerimiento.objects.filter(
            extractor_log__isnull=False
        ).count()
        restantes = total_whatsapp - total
        self.stdout.write(f'  Total whatsapp general: {total_whatsapp}')
        self.stdout.write(f'  Restantes despues del borrado: {restantes}')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: no se borro nada.'))
            return

        # --- 3. Confirmacion ---
        if not force:
            self.stdout.write(self.style.WARNING(
                'ATENCION: Se borraran PERMANENTEMENTE estos requerimientos.'
            ))
            self.stdout.write(self.style.WARNING(
                'Los ExtractorLog, LogEntry y Archivos NO se veran afectados.'
            ))
            confirm = input('  Escribe "si" para confirmar: ')
            if confirm.lower() not in ('si', 's'):
                self.stdout.write(self.style.WARNING('Operacion cancelada.'))
                return

        # --- 4. Ejecutar borrado ---
        with transaction.atomic():
            eliminados, detalle = qs.delete()
            self.stdout.write(
                self.style.SUCCESS(f'  OK: Requerimientos eliminados: {eliminados}')
            )

        self.stdout.write(self.style.SUCCESS(
            '\nOperacion completada exitosamente.'
        ))
