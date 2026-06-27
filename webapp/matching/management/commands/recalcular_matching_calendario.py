"""
Comando: recalcular_matching_calendario
========================================
Ejecuta matching con HybridMatchingSkill (FAISS + scoring) para TODOS los
requerimientos activos y guarda los resultados en MatchResult.

Uso:
    python manage.py recalcular_matching_calendario
    python manage.py recalcular_matching_calendario --score-minimo 70
    python manage.py recalcular_matching_calendario --top-n 10
    python manage.py recalcular_matching_calendario --dry-run
    python manage.py recalcular_matching_calendario --requerimiento-id 123
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalcula matching (HybridMatchingSkill) para todos los requerimientos y guarda en MatchResult'

    def add_arguments(self, parser):
        parser.add_argument(
            '--top-n',
            type=int,
            default=10,
            help='Máximo de matches a guardar por requerimiento (default: 10)'
        )
        parser.add_argument(
            '--score-minimo',
            type=float,
            default=70,
            help='Score minimo para guardar resultados (default: 70)'
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
        top_n = options['top_n']
        score_minimo = options['score_minimo']
        dry_run = options['dry_run']
        req_id = options['requerimiento_id']

        from requerimientos.models import Requerimiento
        from matching.engine import guardar_resultados_matching
        from intelligence.skills.registry import SkillRegistry
        from intelligence.skills.orchestrator import SkillOrchestrator, ExecutionContext
        from intelligence.skills.cache import SkillCache

        # Obtener requerimientos
        if req_id:
            requerimientos = Requerimiento.objects.filter(id=req_id)
        else:
            requerimientos = Requerimiento.objects.all().order_by('-fecha')

        total = requerimientos.count()
        self.stdout.write(f"Total requerimientos a procesar: {total}")
        self.stdout.write(f"  Top-N: {top_n}")
        self.stdout.write(f"  Score minimo: {score_minimo}")
        self.stdout.write(f"  Dry run: {dry_run}")
        self.stdout.write(f"  Motor: HybridMatchingSkill (FAISS + scoring estructural)")

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se ejecutara matching"))
            return

        if total == 0:
            self.stdout.write(self.style.WARNING("No hay requerimientos para procesar"))
            return

        # Preparar orchestrator (una vez)
        registry = SkillRegistry()
        orchestrator = SkillOrchestrator(registry, SkillCache())

        # Procesar
        procesados = 0
        con_match = 0
        errores = 0

        self.stdout.write("\nEjecutando matching híbrido...\n")

        for req in requerimientos:
            try:
                self.stdout.write(
                    f"  [{procesados+1}/{total}] Requerimiento #{req.id}: {str(req)[:60]}...",
                    ending=''
                )

                context = ExecutionContext()
                result = orchestrator.execute_skill('matching_hibrido', {
                    'requerimiento_id': req.id,
                    'top_n': top_n,
                    'umbral_minimo': score_minimo,
                }, context)

                if not result.success or not result.data:
                    self.stdout.write(f" -> Sin matches o error: {result.message}")
                    continue

                matches = result.data.get('matches', [])
                if not matches:
                    self.stdout.write(f" -> Sin matches compatibles")
                    continue

                # Convertir al formato que espera guardar_resultados_matching
                resultados_para_guardar = []
                for m in matches:
                    resultados_para_guardar.append({
                        'propiedad_id': m['property_id'],
                        'score_total': m['score_total'],
                        'score_detalle': m.get('score_detalle', {}),
                        'fase_eliminada': None,
                        'porcentaje_compatibilidad': m['score_total'],
                        'ranking': m.get('ranking'),
                    })

                guardar_resultados_matching(req.id, resultados_para_guardar)
                mejor_score = max(m['score_total'] for m in matches)
                self.stdout.write(
                    f" -> {len(matches)} matches guardados (mejor: {mejor_score:.1f}%)"
                )
                con_match += 1
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
        self.stdout.write(f"  Motor: HybridMatchingSkill")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")
        self.stdout.write("Ahora abre el calendario en /matching/calendar/ para ver los porcentajes.")
