"""
Skills del Sistema Experto Multi-Rol (SPEC v2.0).

Organizadas por categoría de permiso:
- metricas: metricas_globales, reporte_ventas, analisis_rendimiento
- legales: consultar_normativa, revisar_contrato, aspectos_legales
- marketing: campanas_activas, leads_generados, metricas_marketing
- agente: mis_propiedades, mis_requerimientos, mis_matches, portafolio_agente, analizar_oportunidad
- gerencia: equipo_a_cargo, desempeño_agentes, reporte_equipo
- ti: logs_sistema, errores_recientes, estado_servicios
"""

from .metricas import (
    MetricasGlobalesSkill,
    ReporteVentasSkill,
    AnalisisRendimientoSkill,
)
from .legales import (
    ConsultarNormativaSkill,
    RevisarContratoSkill,
    AspectosLegalesSkill,
)
from .marketing import (
    CampanasActivasSkill,
    LeadsGeneradosSkill,
    MetricasMarketingSkill,
)
from .agente import (
    MisPropiedadesSkill,
    MisRequerimientosSkill,
    MisMatchesSkill,
    PortafolioAgenteSkill,
    AnalizarOportunidadSkill,
)
from .gerencia import (
    EquipoACargoSkill,
    DesempenoAgentesSkill,
    ReporteEquipoSkill,
)
from .ti import (
    LogsSistemaSkill,
    ErroresRecientesSkill,
    EstadoServiciosSkill,
)

__all__ = [
    'MetricasGlobalesSkill',
    'ReporteVentasSkill',
    'AnalisisRendimientoSkill',
    'ConsultarNormativaSkill',
    'RevisarContratoSkill',
    'AspectosLegalesSkill',
    'CampanasActivasSkill',
    'LeadsGeneradosSkill',
    'MetricasMarketingSkill',
    'MisPropiedadesSkill',
    'MisRequerimientosSkill',
    'MisMatchesSkill',
    'PortafolioAgenteSkill',
    'AnalizarOportunidadSkill',
    'EquipoACargoSkill',
    'DesempenoAgentesSkill',
    'ReporteEquipoSkill',
    'LogsSistemaSkill',
    'ErroresRecientesSkill',
    'EstadoServiciosSkill',
]
