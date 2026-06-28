"""
Skills de Gerencia — Sistema Experto Multi-Rol (SPEC v2.0).

Skills:
  - equipo_a_cargo (level 3, domain: gerencia)
  - desempeño_agentes (level 3, domain: gerencia)
  - reporte_equipo (level 3, domain: gerencia)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class EquipoACargoSkill(BaseSkill):
    """
    Consulta el equipo de agentes a cargo del usuario.
    Requiere domain 'gerencia'.
    """
    name = "equipo_a_cargo"
    description = (
        "Muestra el equipo de agentes a cargo del usuario: "
        "lista de agentes, su rendimiento, propiedades a cargo, "
        "y métricas del equipo"
    )
    category = "reporte"
    access_level = 3
    required_domain = 'gerencia'
    required_collection = None
    parameters_schema = {
        'detalle': {
            'type': 'boolean',
            'description': 'Incluir detalle por agente',
            'default': False,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        detalle = params.get('detalle', False)

        data = {
            'total_agentes': 8,
            'agentes_activos': 6,
            'agentes_inactivos': 2,
            'ventas_equipo_mes': 12,
            'matches_equipo': 156,
            'agentes': [
                {'nombre': 'María López', 'activo': True, 'ventas': 4, 'propiedades': 15},
                {'nombre': 'Juan Pérez', 'activo': True, 'ventas': 3, 'propiedades': 12},
                {'nombre': 'Pedro Sánchez', 'activo': False, 'ventas': 0, 'propiedades': 8},
            ],
            'cumplimiento_metas': '75%',
        }

        return SkillResult.ok(
            data=data,
            message=f"Tu equipo tiene {data['total_agentes']} agentes. {data['ventas_equipo_mes']} ventas este mes.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class DesempenoAgentesSkill(BaseSkill):
    """
    Evalúa el desempeño individual y grupal de los agentes.
    Requiere domain 'gerencia'.
    """
    name = "desempeno_agentes"
    description = (
        "Evalúa el desempeño de los agentes del equipo: "
        "ranking de ventas, matches generados, cumplimiento de metas, "
        "y detección de agentes que necesitan apoyo"
    )
    category = "reporte"
    access_level = 3
    required_domain = 'gerencia'
    required_collection = None
    parameters_schema = {
        'metric': {
            'type': 'string',
            'description': 'Métrica: "ventas", "matches", "propiedades", "overall"',
            'default': 'overall',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        metric = params.get('metric', 'overall')

        data = {
            'metric': metric,
            'top_performer': {'nombre': 'María López', 'ventas': 4, 'matches': 45},
            'needs_support': [
                {'nombre': 'Pedro Sánchez', 'razon': '0 ventas en 30 días', 'recomendacion': 'Revisar cartera asignada'},
            ],
            'promedio_equipo': {
                'ventas': 2.1,
                'matches': 28,
                'propiedades_gestionadas': 11,
            },
        }

        return SkillResult.ok(
            data=data,
            message=f"Desempeño del equipo evaluado. Top: {data['top_performer']['nombre']}. {len(data['needs_support'])} agente(s) requieren apoyo.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class ReporteEquipoSkill(BaseSkill):
    """
    Genera reportes consolidados del equipo de agentes.
    Requiere domain 'gerencia'.
    """
    name = "reporte_equipo"
    description = (
        "Genera reportes consolidados del equipo de agentes: "
        "resumen de actividad, métricas clave, comparativa "
        "con períodos anteriores y tendencias"
    )
    category = "reporte"
    access_level = 3
    required_domain = 'gerencia'
    required_collection = None
    parameters_schema = {
        'periodo': {
            'type': 'string',
            'description': 'Período: "semana", "mes", "trimestre"',
            'default': 'mes',
        },
        'formato': {
            'type': 'string',
            'description': 'Formato: "resumen", "detallado"',
            'default': 'resumen',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        periodo = params.get('periodo', 'mes')
        formato = params.get('formato', 'resumen')

        data = {
            'periodo': periodo,
            'formato': formato,
            'total_agentes': 8,
            'ventas_periodo': 12,
            'matches_generados': 156,
            'propiedades_publicadas': 45,
            'tasa_exito_matches': '23%',
            'vs_periodo_anterior': {
                'ventas': '+20%',
                'matches': '+15%',
                'propiedades': '+8%',
            },
        }

        return SkillResult.ok(
            data=data,
            message=f"Reporte de equipo del {periodo} generado. {data['ventas_periodo']} ventas, {data['matches_generados']} matches.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True
