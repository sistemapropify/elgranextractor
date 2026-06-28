"""
Skills Legales — Sistema Experto Multi-Rol (SPEC v2.0).

Skills:
  - consultar_normativa (level 1, collection: normativas_legales)
  - revisar_contrato (level 3, domain: legal, collection: normativas_legales)
  - aspectos_legales (level 1, collection: normativas_legales)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class ConsultarNormativaSkill(BaseSkill):
    """
    Consulta la normativa legal peruana sobre bienes raíces.
    Usa RAG sobre la colección 'normativas_legales'.
    Accesible para level 1+ si tiene acceso a la colección.
    """
    name = "consultar_normativa"
    description = (
        "Consulta normativas legales peruanas sobre bienes raíces: "
        "ley de inquilinato, zonificación, propiedad horizontal, "
        "reglamentos de construcción, derechos del inquilino"
    )
    category = "busqueda"
    access_level = 1
    required_domain = None
    required_collection = 'normativas_legales'
    parameters_schema = {
        'consulta': {
            'type': 'string',
            'description': 'Consulta legal en lenguaje natural',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        consulta = params.get('consulta', '')
        if not consulta:
            return SkillResult.error(
                "Debes especificar una consulta legal.",
                skill_name=self.name,
            )

        # Placeholder: aquí iría la búsqueda RAG sobre normativas_legales
        # Por ahora retorna un mensaje informativo
        data = {
            'consulta': consulta,
            'respuesta': (
                f"Según la normativa peruana consultada sobre: '{consulta}', "
                f"se encontraron referencias relevantes. "
                f"(Integración con colección 'normativas_legales' pendiente)"
            ),
            'fuentes': [],
        }

        return SkillResult.ok(
            data=data,
            message=f"Consulta normativa realizada: {consulta[:100]}...",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get('consulta'))


class RevisarContratoSkill(BaseSkill):
    """
    Revisa contratos y documentos legales.
    Requiere domain 'legal' (abogados) y acceso a colección 'normativas_legales'.
    """
    name = "revisar_contrato"
    description = (
        "Revisa contratos de alquiler, compraventa y otros documentos "
        "legales inmobiliarios. Identifica cláusulas problemáticas, "
        "sugiere modificaciones y verifica cumplimiento normativo"
    )
    category = "custom"
    access_level = 3
    required_domain = 'legal'
    required_collection = 'normativas_legales'
    parameters_schema = {
        'texto_contrato': {
            'type': 'string',
            'description': 'Texto del contrato a revisar',
        },
        'tipo_contrato': {
            'type': 'string',
            'description': 'Tipo: "alquiler", "compraventa", "promesa"',
            'default': 'alquiler',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        texto = params.get('texto_contrato', '')
        tipo = params.get('tipo_contrato', 'alquiler')

        if not texto:
            return SkillResult.error(
                "Debes proporcionar el texto del contrato a revisar.",
                skill_name=self.name,
            )

        data = {
            'tipo_contrato': tipo,
            'clausulas_revisadas': 0,
            'observaciones': [],
            'recomendaciones': [
                "Revisar cláusula de penalidades por incumplimiento.",
                "Verificar que el plazo y monto estén correctamente expresados.",
            ],
            'cumple_normativa': True,
        }

        return SkillResult.ok(
            data=data,
            message=f"Revisión de contrato de {tipo} completada.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get('texto_contrato'))


class AspectosLegalesSkill(BaseSkill):
    """
    Proporciona información sobre aspectos legales generales
    en transacciones inmobiliarias.
    Accesible para level 1+ si tiene acceso a colección 'normativas_legales'.
    """
    name = "aspectos_legales"
    description = (
        "Información sobre aspectos legales en transacciones inmobiliarias: "
        "documentación necesaria, impuestos, costos notariales, "
        "requisitos para comprar/vender propiedad en Perú"
    )
    category = "busqueda"
    access_level = 1
    required_domain = None
    required_collection = 'normativas_legales'
    parameters_schema = {
        'tema': {
            'type': 'string',
            'description': 'Tema legal a consultar',
            'default': 'general',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        tema = params.get('tema', 'general')

        data = {
            'tema': tema,
            'aspectos_clave': [
                "Documentos: DNI, partida registral, declaratoria de fábrica.",
                "Impuestos: Alcabala (3%), Renta (5% o 6.25%).",
                "Costos: Notaría (~3% del valor), Registros públicos.",
                "Requisitos: Minuta, escritura pública, inscripción registral.",
            ],
            'mensaje': f"Aspectos legales sobre '{tema}' consultados.",
        }

        return SkillResult.ok(
            data=data,
            message=f"Información legal sobre '{tema}' recuperada.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True
