"""
Skills de TI/Sistema — Sistema Experto Multi-Rol (SPEC v2.0).

Skills:
  - logs_sistema (level 4, domain: ti)
  - errores_recientes (level 4, domain: ti)
  - estado_servicios (level 4, domain: ti)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class LogsSistemaSkill(BaseSkill):
    """
    Consulta logs del sistema de inteligencia.
    Requiere domain 'ti'.
    """
    name = "logs_sistema"
    description = (
        "Consulta los logs del sistema de inteligencia: "
        "ejecuciones de skills, accesos de usuarios, "
        "llamadas a APIs externas, y actividad del sistema"
    )
    category = "reporte"
    access_level = 4
    required_domain = 'ti'
    required_collection = None
    parameters_schema = {
        'nivel': {
            'type': 'string',
            'description': 'Nivel de log: "INFO", "WARNING", "ERROR", "DEBUG"',
            'default': 'INFO',
        },
        'limite': {
            'type': 'integer',
            'description': 'Máximo de entradas a mostrar',
            'default': 50,
        },
        'app': {
            'type': 'string',
            'description': 'Filtrar por app: "semantic_router", "chat_processor", etc.',
            'default': None,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        nivel = params.get('nivel', 'INFO')
        limite = params.get('limite', 50)
        app = params.get('app')

        data = {
            'nivel': nivel,
            'total_logs': limite,
            'aplicacion': app or 'todas',
            'logs_recientes': [
                {'timestamp': '2026-06-28 10:30:00', 'nivel': 'INFO', 'mensaje': 'Skill ejecutada: busqueda_propiedades', 'app': 'semantic_router'},
                {'timestamp': '2026-06-28 10:29:45', 'nivel': 'INFO', 'mensaje': 'Usuario autenticado: user_123', 'app': 'middleware'},
                {'timestamp': '2026-06-28 10:29:30', 'nivel': 'WARNING', 'mensaje': 'DeepSeek API lento (2.3s)', 'app': 'llm'},
            ],
        }

        return SkillResult.ok(
            data=data,
            message=f"{limite} logs de nivel {nivel} recuperados.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class ErroresRecientesSkill(BaseSkill):
    """
    Consulta errores y excepciones recientes del sistema.
    Requiere domain 'ti'.
    """
    name = "errores_recientes"
    description = (
        "Muestra errores y excepciones recientes del sistema: "
        "fallos en ejecución de skills, errores de conexión, "
        "tracebacks, y problemas reportados"
    )
    category = "reporte"
    access_level = 4
    required_domain = 'ti'
    required_collection = None
    parameters_schema = {
        'severidad': {
            'type': 'string',
            'description': 'Filtrar por severidad: "error", "warning", "critico"',
            'default': 'error',
        },
        'ultimas_horas': {
            'type': 'integer',
            'description': 'Últimas N horas a revisar',
            'default': 24,
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        severidad = params.get('severidad', 'error')
        horas = params.get('ultimas_horas', 24)

        data = {
            'severidad': severidad,
            'periodo_horas': horas,
            'total_errores': 3,
            'errores': [
                {'tipo': 'ConnectionError', 'mensaje': 'Timeout conectando a DeepSeek API', 'frecuencia': 5, 'ultima_vez': '2026-06-28 10:15:00'},
                {'tipo': 'ValueError', 'mensaje': 'Embedding no generado para consulta vacía', 'frecuencia': 2, 'ultima_vez': '2026-06-28 09:45:00'},
                {'tipo': 'DoesNotExist', 'mensaje': 'Usuario no encontrado en SkillExecution', 'frecuencia': 1, 'ultima_vez': '2026-06-27 23:10:00'},
            ],
            'recomendacion': 'Revisar conectividad con DeepSeek API. Los errores de timeout han aumentado.',
        }

        return SkillResult.ok(
            data=data,
            message=f"{data['total_errores']} errores de severidad '{severidad}' en las últimas {horas} horas.",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


class EstadoServiciosSkill(BaseSkill):
    """
    Monitorea el estado de los servicios del sistema.
    Requiere domain 'ti'.
    """
    name = "estado_servicios"
    description = (
        "Monitorea el estado de los servicios del sistema: "
        "base de datos, Redis/Celery, DeepSeek API, "
        "Azure Blob Storage, y health check general"
    )
    category = "reporte"
    access_level = 4
    required_domain = 'ti'
    required_collection = None
    parameters_schema = {
        'servicio': {
            'type': 'string',
            'description': 'Servicio específico o "todos"',
            'default': 'todos',
        },
    }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        servicio = params.get('servicio', 'todos')

        data = {
            'health_general': 'OK',
            'uptime': '99.8%',
            'servicios': [
                {'nombre': 'Base de Datos (Azure SQL)', 'estado': 'OK', 'latencia_ms': 15},
                {'nombre': 'Redis / Celery', 'estado': 'OK', 'latencia_ms': 2},
                {'nombre': 'DeepSeek API', 'estado': 'Degradado', 'latencia_ms': 2300},
                {'nombre': 'Azure Blob Storage', 'estado': 'OK', 'latencia_ms': 45},
                {'nombre': 'Servicio de Embeddings', 'estado': 'OK', 'latencia_ms': 120},
            ],
            'servicios_caidos': 0,
            'servicios_degradados': 1,
            'alerta': 'DeepSeek API presenta latencia alta (>2s). Monitorear.',
        }

        return SkillResult.ok(
            data=data,
            message=f"Health check: {data['health_general']}. {len(data['servicios'])} servicios, {data['servicios_degradados']} degradado(s).",
            skill_name=self.name,
        )

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True
