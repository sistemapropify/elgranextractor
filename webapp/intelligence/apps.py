import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class IntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'intelligence'

    def ready(self):
        """
        Inicialización de la aplicación Intelligence.
        
        1. Registra signals (auto-creación de perfiles de inteligencia)
        2. Carga índices FAISS al iniciar la aplicación (en segundo plano)
        3. Registra skills en el SkillRegistry
        """
        # 1. Registrar signals
        try:
            import intelligence.signals  # noqa: F401
            logger.debug("Signals de inteligencia registrados correctamente")
        except Exception as e:
            logger.warning(f"No se pudieron registrar signals: {e}")
        
        # 2. Cargar índices FAISS
        try:
            from .services.faiss_index import FAISSIndexManager
            FAISSIndexManager.load_all()
        except Exception as e:
            logger.warning(f"No se pudieron cargar índices FAISS en startup: {e}")

        # 3. Registrar skills en el SkillRegistry
        try:
            from .skills.registry import SkillRegistry
            from .skills.propiedades.skill import BusquedaPropiedadesSkill
            from .skills.acm_analisis import ACMAnalisisSkill
            from .skills.reporte_precios import ReportePreciosZonaSkill
            from .skills.matching import MatchingOfertaDemandaSkill
            from .skills.busqueda_exacta import BusquedaExactaSkill
            from .skills.formatear_propiedades import FormatearPropiedadesSkill
            from .skills.clasificar_intencion_whatsapp import ClasificarIntencionWhatsAppSkill
            from .skills.examples.math_skills import (
                SumaSkill, RestaSkill, MultiplicacionSkill,
                DivisionSkill, PotenciaSkill, RaizCuadradaSkill,
                EstadisticasBasicasSkill,
            )
            from .skills.examples.data_skills import (
                ContarPalabrasSkill, FiltrarListaSkill,
                OrdenarListaSkill, ResumirTextoSkill,
            )

            registry = SkillRegistry()
            registry.register(BusquedaPropiedadesSkill)
            registry.register(ACMAnalisisSkill)
            registry.register(ReportePreciosZonaSkill)
            registry.register(MatchingOfertaDemandaSkill)
            registry.register(BusquedaExactaSkill)
            registry.register(FormatearPropiedadesSkill)
            registry.register(ClasificarIntencionWhatsAppSkill)
            # NOTA: ResolverContextoSkill eliminado en refactor v2.
            # DeepSeek ahora resuelve el contexto conversacional directamente
            # como parte del prompt de orquestación. Ver services/chat_processor.py
            registry.register(SumaSkill)
            registry.register(RestaSkill)
            registry.register(MultiplicacionSkill)
            registry.register(DivisionSkill)
            registry.register(PotenciaSkill)
            registry.register(RaizCuadradaSkill)
            registry.register(EstadisticasBasicasSkill)
            registry.register(ContarPalabrasSkill)
            registry.register(FiltrarListaSkill)
            registry.register(OrdenarListaSkill)
            registry.register(ResumirTextoSkill)
            logger.info("Skills registradas en SkillRegistry al iniciar Django")
        except Exception as e:
            logger.warning(f"No se pudieron registrar skills en startup: {e}")
