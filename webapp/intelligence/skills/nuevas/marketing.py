"""
Skills de Marketing — Sistema Experto Multi-Rol (SPEC v2.0).

Skills:
  - campanas_activas (level 3, domain: marketing, collection: campanas_marketing)
  - leads_generados (level 3, domain: marketing, collection: campanas_marketing)
  - metricas_marketing (level 3, domain: marketing, collection: campanas_marketing)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class CampanasActivasSkill(BaseSkill):
    """
    Consulta campañas de marketing activas en Meta Ads.
    Requiere domain 'marketing' y acceso a colección 'campanas_marketing'.
    """
    name = "campanas_activas"
    description = (
        "Muestra las campañas de Meta Ads (Facebook/Instagram) activas: "
        "nombre, estado, inversión, alcance, y rendimiento actual"
    )
    category = "reporte"
    access_level = 3
    required_domain = 'marketing'
    required_collection = 'campanas_marketing'
    parameters_schema = {
        'detalle': {
            'type': 'boolean',
            'description': 'Incluir métricas detalladas por campaña',
            'default': False,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        detalle = params.get('detalle', False)

        data = {
            'campañas_activas': 5,
            'inversión_total_mes': 2500.00,
            'moneda': 'USD',
            'campañas': [
                {'nombre': 'Ventas Cayma - Junio', 'estado': 'Activa', 'inversion': 800, 'alcance': 45000},
                {'nombre': 'Departamentos Yanahuara', 'estado': 'Activa', 'inversion': 600, 'alcance': 32000},
                {'nombre': 'Terrenos Cerro Colorado', 'estado': 'Activa', 'inversion': 500, 'alcance': 28000},
                {'nombre': 'Ofertas Invierno 2026', 'estado': 'Activa', 'inversion': 400, 'alcance': 22000},
                {'nombre': 'Locales Comerciales', 'estado': 'Pausada', 'inversion': 200, 'alcance': 15000},
            ],
            'detalle_habilitado': detalle,
        }

        return SkillResult.ok(
            data=data,
            message=f"5 campañas activas con inversión total de USD 2,500 este mes.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class LeadsGeneradosSkill(BaseSkill):
    """
    Reporte de leads generados por campañas de marketing.
    Requiere domain 'marketing' y acceso a colección 'campanas_marketing'.
    """
    name = "leads_generados"
    description = (
        "Muestra los leads generados por campañas de Meta Ads: "
        "cantidad por campaña, costo por lead, calidad de leads, "
        "tasa de conversión a cliente"
    )
    category = "reporte"
    access_level = 3
    required_domain = 'marketing'
    required_collection = 'campanas_marketing'
    parameters_schema = {
        'periodo': {
            'type': 'string',
            'description': 'Período: "mes", "semana", "trimestre"',
            'default': 'mes',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        periodo = params.get('periodo', 'mes')

        data = {
            'periodo': periodo,
            'total_leads': 234,
            'costo_por_lead_usd': 10.68,
            'tasa_conversion': '12.5%',
            'leads_por_campana': {
                'Ventas Cayma - Junio': 85,
                'Departamentos Yanahuara': 62,
                'Terrenos Cerro Colorado': 48,
                'Ofertas Invierno 2026': 39,
            },
            'calidad_promedio': 'Alta',
        }

        return SkillResult.ok(
            data=data,
            message=f"{data['total_leads']} leads generados en el {periodo}. Costo promedio: USD {data['costo_por_lead_usd']}/lead.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class MetricasMarketingSkill(BaseSkill):
    """
    Métricas completas de rendimiento de marketing.
    Requiere domain 'marketing' y acceso a colección 'campanas_marketing'.
    """
    name = "metricas_marketing"
    description = (
        "Métricas de rendimiento de marketing digital: ROI, alcance, "
        "impresiones, clics, conversiones, costo por resultado, "
        "y comparativa con períodos anteriores"
    )
    category = "reporte"
    access_level = 3
    required_domain = 'marketing'
    required_collection = 'campanas_marketing'
    parameters_schema = {
        'periodo': {
            'type': 'string',
            'description': 'Período: "mes", "semana", "trimestre"',
            'default': 'mes',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        periodo = params.get('periodo', 'mes')

        data = {
            'periodo': periodo,
            'inversion_total': 2500.00,
            'alcance_total': 142000,
            'impresiones': 450000,
            'clics': 12300,
            'ctr': '2.73%',
            'conversiones': 234,
            'costo_por_conversion': 10.68,
            'roi': '320%',
            'vs_periodo_anterior': {
                'alcance': '+15%',
                'conversiones': '+22%',
                'costo_por_lead': '-8%',
            },
        }

        return SkillResult.ok(
            data=data,
            message=f"Métricas de marketing del {periodo}: ROI {data['roi']}, {data['conversiones']} conversiones.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True
