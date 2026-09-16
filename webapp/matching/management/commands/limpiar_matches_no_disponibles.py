"""
Comando: limpiar_matches_no_disponibles
========================================
Marca `fase_eliminada = 'propiedad_no_disponible'` en los MatchResult cuya
propiedad ya no está en cartera activa (is_visible = 1 y property_status_id = 3,
es decir, estado "Disponible").

Esto corrige el defecto de negocio: matching contra propiedades que ya se
vendieron, reservaron, pausaron o están en Draft.

Uso:
    python manage.py limpiar_matches_no_disponibles
    python manage.py limpiar_matches_no_disponibles --dry-run
"""
import logging

from django.core.management.base import BaseCommand
from django.db import connections

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Marca MatchResult cuya propiedad ya no está disponible en cartera activa'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo reportar, no modificar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        from matching.models import MatchResult

        propiedad_ids = list(
            MatchResult.objects.filter(fase_eliminada__isnull=True)
            .values_list('propiedad_id', flat=True)
            .distinct()
        )
        if not propiedad_ids:
            self.stdout.write(self.style.WARNING('No hay MatchResult activos.'))
            return

        disponibles = set()
        with connections['propifai'].cursor() as cur:
            # SQL Server no permite más de 2100 parámetros: procesar por lotes.
            for i in range(0, len(propiedad_ids), 500):
                lote = propiedad_ids[i:i + 500]
                placeholders = ', '.join(['%s'] * len(lote))
                cur.execute(
                    f"SELECT id FROM dbo.property "
                    f"WHERE is_visible = 1 AND property_status_id = 3 "
                    f"AND id IN ({placeholders})",
                    lote,
                )
                for (pid,) in cur.fetchall():
                    disponibles.add(pid)

        no_disponibles = [pid for pid in propiedad_ids if pid not in disponibles]
        if not no_disponibles:
            self.stdout.write(self.style.SUCCESS(
                'Todos los MatchResult apuntan a propiedades disponibles. Nada que limpiar.'
            ))
            return

        qs = MatchResult.objects.filter(
            fase_eliminada__isnull=True,
            propiedad_id__in=no_disponibles,
        )
        total = qs.count()
        self.stdout.write(
            f'Se marcarán {total} MatchResult como "propiedad_no_disponible" '
            f'({len(no_disponibles)} propiedades fuera de cartera activa).'
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: no se modificó nada.'))
            return

        actualizados = qs.update(fase_eliminada='propiedad_no_disponible')
        self.stdout.write(self.style.SUCCESS(f'{actualizados} MatchResult actualizados.'))
