"""
Management command: recalibrar_agentes

Job nocturno que recalibra thresholds del Supervisor basado en feedback
acumulado en EpisodicMemory y resultados de ejecuciones fallidas.

SPEC: refactor_plataforma_agentes.md — Fase 9
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand
from django.db.models import Q, Count, Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Recalibra thresholds del Supervisor basado en feedback "
        "acumulado y ejecuciones fallidas. Se ejecuta como job nocturno."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Modo simulación: no persiste cambios, solo reporta',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Días hacia atrás para analizar (default: 7)',
        )
        parser.add_argument(
            '--threshold-key',
            type=str,
            default='supervisor_threshold',
            help='Key en AgentConfig para el threshold (default: supervisor_threshold)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        days = options.get('days', 7)
        threshold_key = options.get('threshold_key', 'supervisor_threshold')

        self.stdout.write(f"[Fase9] Iniciando recalibración ({'DRY RUN' if dry_run else 'producción'})")
        self.stdout.write(f"[Fase9] Analizando últimos {days} días")

        # ── 1. Extraer episodios con feedback negativo ──
        casos_problema = self._get_problematic_cases(days)
        self.stdout.write(
            f"[Fase9] Casos con feedback negativo: {casos_problema['negative_feedback']}"
        )
        self.stdout.write(
            f"[Fase9] Ejecuciones fallidas: {casos_problema['failed_executions']}"
        )

        # ── 2. Agrupar por agente ──
        por_agente = self._group_by_agent(casos_problema)
        for agent_name, stats in por_agente.items():
            self.stdout.write(
                f"  {agent_name}: {stats['total']} casos, "
                f"{stats['failed']} fallos ({stats.get('failure_rate', 0):.1%})"
            )

        # ── 3. Calcular nuevo threshold ──
        nuevo_threshold = self._calcular_threshold(casos_problema, por_agente)
        threshold_actual = self._get_current_threshold(threshold_key)

        self.stdout.write(
            f"[Fase9] Threshold actual: {threshold_actual:.4f}"
        )
        self.stdout.write(
            f"[Fase9] Threshold propuesto: {nuevo_threshold:.4f} "
            f"({'aumenta' if nuevo_threshold > threshold_actual else 'disminuye'})"
        )

        # ── 4. Generar candidatos a templates ──
        templates_sugeridos = self._generate_template_candidates(casos_problema)
        if templates_sugeridos:
            self.stdout.write(
                f"[Fase9] {len(templates_sugeridos)} candidatos a template "
                f"detectados (requieren revisión manual)"
            )
            for t in templates_sugeridos[:5]:  # mostrar top 5
                self.stdout.write(f"  - [{t['agent']}] {t['query'][:80]}...")

        # ── 5. Persistir cambios (si no es dry-run) ──
        if not dry_run:
            self._save_threshold(threshold_key, nuevo_threshold)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[Fase9] Threshold actualizado: {threshold_actual:.4f} → {nuevo_threshold:.4f}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "[Fase9] DRY RUN: cambios no persistidos. "
                    "Ejecutar sin --dry-run para aplicar."
                )
            )

        # ── 6. Reporte final ──
        self._generate_report(casos_problema, por_agente, threshold_actual, nuevo_threshold)

    # ── Métodos de análisis ──────────────────────────────────────────────

    def _get_problematic_cases(self, days: int) -> Dict[str, Any]:
        """
        Extrae episodios problemáticos de los últimos N días.

        Returns:
            Dict con casos de feedback negativo y ejecuciones fallidas
        """
        from ...models import EpisodicMemory, AgentExecution

        since = timezone.now() - timedelta(days=days)

        # Feedback negativo
        negative_feedback = EpisodicMemory.objects.filter(
            created_at__gte=since,
            feedback__thumbs_up=False,
        )

        # También considerar episodios sin feedback (neutro) con baja importancia
        low_importance = EpisodicMemory.objects.filter(
            created_at__gte=since,
            importance_score__lt=0.3,
        )

        # Ejecuciones de agentes fallidas
        failed_executions = AgentExecution.objects.filter(
            created_at__gte=since,
            success=False,
        )

        return {
            'negative_feedback': negative_feedback.count(),
            'low_importance': low_importance.count(),
            'failed_executions': failed_executions.count(),
            'negative_list': list(negative_feedback.values('id', 'user_message', 'importance_score')[:100]),
            'failed_list': list(failed_executions.values('id', 'agent_name', 'error_message')[:100]),
            'since': since,
        }

    def _group_by_agent(self, casos: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agrupa casos problemáticos por agente.

        Returns:
            Dict {agent_name: {total, failed, failure_rate, queries}}
        """
        from ...models import AgentExecution

        since = casos.get('since', timezone.now() - timedelta(days=7))

        # Estadísticas por agente desde AgentExecution
        stats = AgentExecution.objects.filter(
            created_at__gte=since,
        ).values('agent_name').annotate(
            total=Count('id'),
            failed=Count('id', filter=Q(success=False)),
        )

        result = {}
        for s in stats:
            name = s['agent_name']
            total = s['total']
            failed = s['failed']
            result[name] = {
                'total': total,
                'failed': failed,
                'success': total - failed,
                'failure_rate': failed / total if total > 0 else 0,
            }

        return result

    def _calcular_threshold(
        self,
        casos: Dict[str, Any],
        por_agente: Dict[str, Any],
    ) -> float:
        """
        Calcula el threshold óptimo del Supervisor.

        Estrategia (calibración empírica):
        - Si hay muchas ejecuciones fallidas → aumentar threshold (más selectivo)
        - Si hay pocos matches y mucho feedback negativo → bajar threshold (más permisivo)
        - El threshold se mueve en pasos de 0.05, máximo 0.10 por recalibración

        Returns:
            Nuevo threshold (float entre 0.25 y 0.85)
        """
        threshold_actual = self._get_current_threshold('supervisor_threshold')
        adjustment = 0.0

        # Factor 1: Tasa de fallos general
        total_ejecuciones = sum(s['total'] for s in por_agente.values())
        total_fallos = sum(s['failed'] for s in por_agente.values())

        if total_ejecuciones > 0:
            failure_rate = total_fallos / total_ejecuciones
            if failure_rate > 0.3:
                # Muchos fallos → más selectivo
                adjustment += 0.05
                logger.info(
                    f"[Fase9] Alta tasa de fallos ({failure_rate:.1%}): "
                    f"aumentando threshold +0.05"
                )
            elif failure_rate < 0.1:
                # Pocos fallos → se puede relajar
                adjustment -= 0.02
                logger.info(
                    f"[Fase9] Baja tasa de fallos ({failure_rate:.1%}): "
                    f"disminuyendo threshold -0.02"
                )

        # Factor 2: Feedback negativo
        negative_count = casos.get('negative_feedback', 0)
        if negative_count > 20:
            # Mucho feedback negativo → más selectivo
            adjustment += 0.03
            logger.info(
                f"[Fase9] Feedback negativo alto ({negative_count}): "
                f"aumentando threshold +0.03"
            )
        elif negative_count < 3 and total_ejecuciones > 50:
            # Poco feedback negativo y muchas ejecuciones → relajar
            adjustment -= 0.01
            logger.info(
                f"[Fase9] Feedback negativo bajo ({negative_count}): "
                f"disminuyendo threshold -0.01"
            )

        # Limitar el ajuste máximo
        adjustment = max(-0.10, min(0.10, adjustment))

        # Calcular nuevo threshold dentro de límites seguros
        nuevo = max(0.25, min(0.85, threshold_actual + adjustment))

        return round(nuevo, 4)

    def _generate_template_candidates(self, casos: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Genera candidatos a nuevos templates para el Supervisor.

        Analiza consultas con feedback negativo que no tuvieron match
        con ningún agente, y las propone como nuevos templates.

        Returns:
            Lista de {agent, query, reason}
        """
        candidates = []

        # Consultas de episodios con feedback negativo
        for ep in casos.get('negative_list', []):
            query = ep.get('user_message', '')
            if query and len(query) > 10:
                # Determinar a qué agente podría pertenecer
                agent = self._suggest_agent_for_query(query)
                if agent:
                    candidates.append({
                        'agent': agent,
                        'query': query,
                        'reason': 'feedback_negativo',
                    })

        return candidates

    def _suggest_agent_for_query(self, query: str) -> Optional[str]:
        """
        Sugiere a qué agente pertenece una consulta basado en palabras clave.

        Returns:
            Nombre del agente sugerido o None
        """
        q = query.lower()

        # Keywords por agente
        if any(kw in q for kw in ['propiedad', 'casa', 'departamento', 'terreno',
                                   'alquiler', 'venta', 'comprar', 'busco']):
            return 'agente_propiedades'
        elif any(kw in q for kw in ['mercado', 'precio', 'campaña', 'marketing',
                                      'anuncio', 'facebook', 'lead']):
            return 'agente_mercado'
        elif any(kw in q for kw in ['requerimiento', 'match', 'cliente',
                                      'necesito', 'busca']):
            return 'agente_requerimientos'

        return None

    # ── Persistencia ────────────────────────────────────────────────────

    def _get_current_threshold(self, key: str) -> float:
        """
        Obtiene el threshold actual desde AgentConfig o default.

        Returns:
            Threshold actual (float)
        """
        try:
            from ...models import AppConfig as AgentConfig
            # Usar AppConfig como almacén de configuración
            config = AgentConfig.objects.filter(id=key).first()
            if config and config.config:
                return float(config.config.get('value', 0.45))
        except Exception:
            pass
        return 0.45

    def _save_threshold(self, key: str, value: float) -> None:
        """
        Persiste el nuevo threshold en AgentConfig.

        Args:
            key: Nombre de la configuración
            value: Nuevo valor del threshold
        """
        try:
            from ...models import AppConfig as AgentConfig
            config, created = AgentConfig.objects.update_or_create(
                id=key,
                defaults={
                    'name': 'Supervisor Threshold',
                    'level': 5,
                    'is_active': True,
                    'config': {
                        'value': value,
                        'updated_at': timezone.now().isoformat(),
                        'previous_value': self._get_current_threshold(key),
                    },
                    'capabilities': {'type': 'threshold'},
                },
            )
            if created:
                logger.info(f"[Fase9] Config '{key}' creada con value={value}")
            else:
                logger.info(f"[Fase9] Config '{key}' actualizada: {value}")
        except Exception as e:
            logger.error(f"[Fase9] Error persistendo threshold: {e}")

    # ── Reporte ─────────────────────────────────────────────────────────

    def _generate_report(
        self,
        casos: Dict[str, Any],
        por_agente: Dict[str, Any],
        threshold_actual: float,
        nuevo_threshold: float,
    ) -> None:
        """
        Genera reporte de la recalibración.

        Args:
            casos: Casos problemáticos analizados
            por_agente: Estadísticas por agente
            threshold_actual: Valor anterior del threshold
            nuevo_threshold: Nuevo valor del threshold
        """
        report = {
            'fecha': timezone.now().isoformat(),
            'threshold_anterior': threshold_actual,
            'threshold_nuevo': nuevo_threshold,
            'cambio': round(nuevo_threshold - threshold_actual, 4),
            'casos_analizados': {
                'feedback_negativo': casos.get('negative_feedback', 0),
                'importancia_baja': casos.get('low_importance', 0),
                'ejecuciones_fallidas': casos.get('failed_executions', 0),
            },
            'por_agente': por_agente,
        }

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("REPORTE DE RECALIBRACIÓN")
        self.stdout.write("=" * 60)
        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False))
        self.stdout.write("=" * 60)
