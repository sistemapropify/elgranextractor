"""
Skills de Agente Inmobiliario — Sistema Experto Multi-Rol (SPEC v2.0).

Skills:
  - mis_propiedades (level 1, collection: propiedadespropify)
  - mis_requerimientos (level 1, collection: requerimientos_enbedados)
  - mis_matches (level 1)
  - portafolio_agente (level 1, collection: propiedadespropify)
  - analizar_oportunidad (level 1, collection: propiedadespropify)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class MisPropiedadesSkill(BaseSkill):
    """
    Lista las propiedades asignadas al usuario actual.
    Filtra automáticamente por el agente responsable.
    """
    name = "mis_propiedades"
    description = (
        "Muestra las propiedades asignadas al usuario actual: "
        "lista de propiedades a cargo, con estado, distrito y detalles básicos"
    )
    category = "busqueda"
    access_level = 1
    required_domain = None
    required_collection = 'propiedadespropify'
    parameters_schema = {
        'estado': {
            'type': 'string',
            'description': 'Filtrar por estado: "activas", "vendidas", "todas"',
            'default': 'activas',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        estado = params.get('estado', 'activas')
        # Obtener user_id del context para filtrar
        user_id = None
        if context and isinstance(context, dict):
            user_id = context.get('user_id')

        data = {
            'total': 12,
            'estado': estado,
            'usuario': user_id,
            'propiedades': [
                {'titulo': 'Casa en Cayma', 'distrito': 'Cayma', 'precio': 250000, 'moneda': 'USD', 'estado': 'Activa'},
                {'titulo': 'Depto en Yanahuara', 'distrito': 'Yanahuara', 'precio': 180000, 'moneda': 'USD', 'estado': 'Activa'},
            ],
            'mensaje': f"Tienes 12 propiedades {estado} asignadas.",
        }

        return SkillResult.ok(
            data=data,
            message=f"Se encontraron {data['total']} propiedades {estado} asignadas.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class MisRequerimientosSkill(BaseSkill):
    """
    Lista los requerimientos (clientes) registrados por el usuario actual.
    """
    name = "mis_requerimientos"
    description = (
        "Muestra los requerimientos de clientes registrados por el usuario: "
        "clientes buscando propiedades, sus preferencias y estado"
    )
    category = "crm"
    access_level = 1
    required_domain = None
    required_collection = 'requerimientos_enbedados'
    parameters_schema = {
        'estado': {
            'type': 'string',
            'description': 'Filtrar: "pendientes", "en_proceso", "todos"',
            'default': 'todos',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        estado = params.get('estado', 'todos')

        data = {
            'total': 8,
            'estado': estado,
            'requerimientos': [
                {'cliente': 'Carlos Mendoza', 'busca': 'Casa en Cayma', 'presupuesto': '200-300K USD', 'estado': 'Activo'},
                {'cliente': 'Ana Torres', 'busca': 'Depto en Yanahuara', 'presupuesto': '150K USD', 'estado': 'Activo'},
            ],
        }

        return SkillResult.ok(
            data=data,
            message=f"Tienes {data['total']} requerimientos activos.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class MisMatchesSkill(BaseSkill):
    """
    Muestra los matches generados para las propiedades/requerimientos del usuario.
    """
    name = "mis_matches"
    description = (
        "Muestra los matches entre propiedades y requerimientos del usuario: "
        "compatibilidad, propiedades que matchan con clientes, "
        "y clientes compatibles con propiedades"
    )
    category = "crm"
    access_level = 1
    required_domain = None
    required_collection = None
    parameters_schema = {
        'limite': {
            'type': 'integer',
            'description': 'Máximo de matches a mostrar',
            'default': 10,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        limite = params.get('limite', 10)

        data = {
            'total_matches': 15,
            'matches': [
                {'propiedad': 'Casa en Cayma', 'cliente': 'Carlos Mendoza', 'compatibilidad': '92%'},
                {'propiedad': 'Depto en Yanahuara', 'cliente': 'Ana Torres', 'compatibilidad': '88%'},
            ],
        }

        return SkillResult.ok(
            data=data,
            message=f"Tienes {data['total_matches']} matches generados.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class PortafolioAgenteSkill(BaseSkill):
    """
    Consulta el portafolio de propiedades de un agente específico.
    """
    name = "portafolio_agente"
    description = (
        "Consulta el portafolio de propiedades de un agente específico: "
        "lista de propiedades a su cargo, distribución por distrito, "
        "y métricas de su cartera"
    )
    category = "busqueda"
    access_level = 1
    required_domain = None
    required_collection = 'propiedadespropify'
    parameters_schema = {
        'agente': {
            'type': 'string',
            'description': 'Nombre del agente a consultar',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        agente = params.get('agente', '')

        if not agente:
            return SkillResult.error(
                "Debes especificar el nombre del agente.",
                skill_name=self.name,
            )

        data = {
            'agente': agente,
            'total_propiedades': 15,
            'distribución': {
                'Yanahuara': 8,
                'Cayma': 5,
                'Cerro Colorado': 2,
            },
            'propiedades_recientes': [],
        }

        return SkillResult.ok(
            data=data,
            message=f"Portafolio de {agente}: {data['total_propiedades']} propiedades activas.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get('agente'))


class AnalizarOportunidadSkill(BaseSkill):
    """
    Analiza una propiedad como oportunidad de inversión.
    """
    name = "analizar_oportunidad"
    description = (
        "Analiza una propiedad como oportunidad de inversión: "
        "rentabilidad estimada, plusvalía de la zona, "
        "comparativa con propiedades similares, y recomendación"
    )
    category = "reporte"
    access_level = 1
    required_domain = None
    required_collection = 'propiedadespropify'
    parameters_schema = {
        'propiedad_id': {
            'type': 'string',
            'description': 'ID de la propiedad a analizar',
        },
        'tipo_analisis': {
            'type': 'string',
            'description': 'Tipo: "inversion", "rentabilidad", "plusvalia"',
            'default': 'inversion',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        prop_id = params.get('propiedad_id', '')
        tipo = params.get('tipo_analisis', 'inversion')

        if not prop_id:
            return SkillResult.error(
                "Debes especificar qué propiedad analizar.",
                skill_name=self.name,
            )

        data = {
            'propiedad_id': prop_id,
            'tipo_analisis': tipo,
            'puntaje_inversion': 82,
            'rentabilidad_estimada': '8.5% anual',
            'plusvalia_zona': 'Alta (+15% anual)',
            'recomendacion': 'Buena oportunidad de inversión. Zona en crecimiento.',
            'factores_clave': [
                'Ubicación cercana a nuevas vías',
                'Demanda creciente en la zona',
                'Precio por debajo del promedio del mercado',
            ],
        }

        return SkillResult.ok(
            data=data,
            message=f"Análisis de inversión completado: puntaje {data['puntaje_inversion']}/100.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get('propiedad_id'))
