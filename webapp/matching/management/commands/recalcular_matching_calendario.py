"""
Comando: recalcular_matching_calendario
========================================
Ejecuta matching para TODOS los requerimientos activos y guarda los resultados
en MatchResult para que se vean en el calendario de matching.

Uso:
    python manage.py recalcular_matching_calendario
    python manage.py recalcular_matching_calendario --limite-propiedades 50
    python manage.py recalcular_matching_calendario --score-minimo 70
    python manage.py recalcular_matching_calendario --dry-run
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalcula matching para todos los requerimientos y guarda en MatchResult'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite-propiedades',
            type=int,
            default=100,
            help='Limite de propiedades a evaluar por requerimiento (default: 100)'
        )
        parser.add_argument(
            '--score-minimo',
            type=float,
            default=0,
            help='Score minimo para guardar resultados (default: 0 = todos)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo contar, no ejecutar matching'
        )
        parser.add_argument(
            '--requerimiento-id',
            type=int,
            default=None,
            help='Ejecutar solo para un requerimiento especifico'
        )

    def handle(self, *args, **options):
        limite_propiedades = options['limite_propiedades']
        score_minimo = options['score_minimo']
        dry_run = options['dry_run']
        req_id = options['requerimiento_id']

        from requerimientos.models import Requerimiento
        from matching.engine import ejecutar_matching_requerimiento, guardar_resultados_matching
        from propifai.models import PropifaiProperty

        # Obtener requerimientos
        if req_id:
            requerimientos = Requerimiento.objects.filter(id=req_id)
        else:
            requerimientos = Requerimiento.objects.all().order_by('-fecha')

        total = requerimientos.count()
        self.stdout.write(f"Total requerimientos a procesar: {total}")
        self.stdout.write(f"  Limite propiedades: {limite_propiedades}")
        self.stdout.write(f"  Score minimo: {score_minimo}")
        self.stdout.write(f"  Dry run: {dry_run}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se ejecutara matching"))
            return

        if total == 0:
            self.stdout.write(self.style.WARNING("No hay requerimientos para procesar"))
            return

        # Obtener propiedades (una vez para todos)
        self.stdout.write("\nCargando propiedades...")
        propiedades = list(PropifaiProperty.objects.all()[:limite_propiedades])
        self.stdout.write(f"  {len(propiedades)} propiedades cargadas")

        # Procesar
        procesados = 0
        con_match = 0
        errores = 0

        self.stdout.write("\nEjecutando matching masivo...\n")

        for req in requerimientos:
            try:
                self.stdout.write(f"  [{procesados+1}/{total}] Requerimiento #{req.id}: {str(req)[:60]}...", ending='')

                resultados, estadisticas = ejecutar_matching_requerimiento(
                    req.id,
                    propiedades=propiedades
                )

                # Filtrar por score minimo
                if score_minimo > 0:
                    resultados = [r for r in resultados if r['score_total'] >= score_minimo]

                if resultados:
                    guardar_resultados_matching(req.id, resultados)
                    mejor_score = max(r['score_total'] for r in resultados)
                    self.stdout.write(f" -> {len(resultados)} matches (mejor: {mejor_score:.1f}%)")
                    con_match += 1
                else:
                    self.stdout.write(f" -> Sin matches compatibles")
            except Exception as e:
                self.stdout.write(f" -> ERROR: {e}")
                logger.error(f"Error procesando requerimiento #{req.id}: {e}")
                errores += 1

            procesados += 1

        # Resumen final
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("PROCESO COMPLETADO"))
        self.stdout.write(f"  Total procesados: {procesados}")
        self.stdout.write(f"  Con match guardado: {con_match}")
        self.stdout.write(f"  Errores: {errores}")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")
        self.stdout.write("Ahora abre el calendario en /matching/calendar/ para ver los porcentajes.")
