"""
Skills de Métricas Globales — Sistema Experto Multi-Rol (SPEC v2.0).

Skills:
  - metricas_globales (level 5): KPIs generales de la empresa
  - reporte_ventas (level 5): Reportes detallados de ventas
  - analisis_rendimiento (level 5): Rendimiento de agentes y platforma
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class MetricasGlobalesSkill(BaseSkill):
    """
    Métricas globales del negocio: KPIs, ventas, matches, agentes activos.
    Solo accesible para level 5 (CEO/directivos).
    """
    name = "metricas_globales"
    description = (
        "Obtiene métricas globales del sistema: ventas del mes, "
        "propiedades publicadas, matches generados, agentes activos, "
        "y KPIs generales del negocio"
    )
    category = "reporte"
    access_level = 5
    required_domain = None
    required_collection = None
    parameters_schema = {
        'periodo': {
            'type': 'string',
            'description': 'Período: "mes", "semana", "trimestre", "año"',
            'default': 'mes',
        },
        'detalle': {
            'type': 'boolean',
            'description': 'Si se incluye desglose detallado',
            'default': False,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        """
        Ejecuta consulta de métricas globales.
        Por ahora retorna un placeholder. La integración con datos reales
        se implementará cuando los modelos de ventas estén definidos.
        """
        periodo = params.get('periodo', 'mes')
        detalle = params.get('detalle', False)

        # Placeholder: aquí iría la lógica real de consulta a BD
        data = {
            'periodo': periodo,
            'detalle': detalle,
            'total_propiedades': 145,
            'vendidas': 23,
            'tasa_venta': '15.9%',
            'agentes_activos': 87,
            'total_agentes': 120,
            'matches_generados': 1234,
            'matches_alta_compatibilidad': '34%',
            'mensaje': f"Resumen ejecutivo - Últimos 30 días. {23} propiedades vendidas de {145} publicadas.",
        }

        return SkillResult.ok(
            data=data,
            message=(
                f"Resumen ejecutivo del {periodo}: "
                f"{data['total_propiedades']} propiedades publicadas, "
                f"{data['vendidas']} vendidas ({data['tasa_venta']}). "
                f"{data['matches_generados']} matches generados."
            ),
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class ReporteVentasSkill(BaseSkill):
    """
    Reporte detallado de ventas por período, distrito, tipo de propiedad.
    Solo accesible para level 5 (CEO/directivos).
    """
    name = "reporte_ventas"
    description = (
        "Genera reportes detallados de ventas: por período, distrito, "
        "tipo de propiedad, agente. Incluye comparativas y tendencias"
    )
    category = "reporte"
    access_level = 5
    required_domain = None
    required_collection = None
    parameters_schema = {
        'periodo': {
            'type': 'string',
            'description': 'Período del reporte',
            'default': 'mes',
        },
        'distrito': {
            'type': 'string',
            'description': 'Filtrar por distrito (opcional)',
            'default': None,
        },
        'tipo_propiedad': {
            'type': 'string',
            'description': 'Filtrar por tipo (opcional)',
            'default': None,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        periodo = params.get('periodo', 'mes')
        distrito = params.get('distrito')
        tipo = params.get('tipo_propiedad')

        data = {
            'periodo': periodo,
            'filtros': {
                'distrito': distrito,
                'tipo_propiedad': tipo,
            },
            'total_ventas': 23,
            'monto_total_usd': 4500000,
            'monto_total_pen': 16500000,
            'transacciones_por_distrito': {
                'Cayma': 8,
                'Yanahuara': 6,
                'Cerro Colorado': 4,
                'Bustamante': 3,
                'Otros': 2,
            },
            'mensaje': f"Reporte de ventas del {periodo}: 23 transacciones por USD 4,500,000.",
        }

        return SkillResult.ok(
            data=data,
            message=f"Reporte de ventas del {periodo} generado.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class AnalisisRendimientoSkill(BaseSkill):
    """
    Análisis de rendimiento de agentes y plataforma.
    Solo accesible para level 5 (CEO/directivos).
    """
    name = "analisis_rendimiento"
    description = (
        "Analiza el rendimiento de agentes: ranking de ventas, "
        "matches generados, propiedades publicadas. "
        "Incluye top y bottom performers"
    )
    category = "reporte"
    access_level = 5
    required_domain = None
    required_collection = None
    parameters_schema = {
        'metric': {
            'type': 'string',
            'description': 'Métrica: "ventas", "matches", "propiedades", "overall"',
            'default': 'overall',
        },
        'limite': {
            'type': 'integer',
            'description': 'Top N agentes a mostrar',
            'default': 10,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        metric = params.get('metric', 'overall')
        limite = params.get('limite', 10)

        data = {
            'metric': metric,
            'top_agentes': [
                {'nombre': 'María López', 'ventas': 5, 'matches': 45},
                {'nombre': 'Juan Pérez', 'ventas': 4, 'matches': 38},
                {'nombre': 'Carlos Ruiz', 'ventas': 3, 'matches': 42},
            ],
            'total_agentes_activos': 87,
            'promedio_ventas_agente': 2.1,
            'mensaje': f"Top {limite} agentes por {metric} analizado.",
        }

        return SkillResult.ok(
            data=data,
            message=f"Análisis de rendimiento por {metric} completado.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True
