import logging
import time
import os
import sys

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
        4. Pre-calcula embeddings del Semantic Router (F1-001)
        5. Pre-carga modelo de embeddings (SPEC-014)
        """
        # ── Verificar si estamos en proceso principal ──
        # Evitar precarga durante migraciones, collectstatic, shell, test
        # CRITICO: Incluir gunicorn para evitar que workers carguen el modelo
        # de embeddings (1GB+) en el hilo principal, lo que causa OOM/restarts
        # en Azure App Service (tiers básicos con ~2GB RAM).
        #
        # FIX-504: Usar os.path.basename() para detectar gunicorn porque
        # en Azure App Service sys.argv[0] es la ruta completa
        # (/home/site/antenv/bin/gunicorn), no solo 'gunicorn'.
        # Además, agregar variable de entorno PRODUCTION=true como guardia
        # explícito para entornos productivos.
        _cmd = os.path.basename(sys.argv[0]) if sys.argv else ''
        _is_gunicorn = _cmd == 'gunicorn' or any('gunicorn' in a for a in sys.argv)
        _is_production = os.environ.get('PRODUCTION', '').lower() in ('true', '1', 'yes')
        _should_skip = any([
            'migrate' in sys.argv,
            'makemigrations' in sys.argv,
            'collectstatic' in sys.argv,
            'flush' in sys.argv,
            'test' in sys.argv,
            'shell' in sys.argv,
            _is_gunicorn,                # FIX-504: detecta gunicorn incluso si es ruta completa
            _is_production,              # FIX-504: variable PRODUCTION=true salta todo lo pesado
            os.environ.get('RUN_MAIN') != 'true' and 'runserver' in sys.argv,
        ])
        if _should_skip:
            logger.debug(
                "Saltando inicialización pesada "
                f"(gunicorn={_is_gunicorn}, production={_is_production})"
            )
        else:
            self._preload_models()

        # 1. Registrar signals
        try:
            import intelligence.signals  # noqa: F401
            logger.debug("Signals de inteligencia registrados correctamente")
        except Exception as e:
            logger.warning(f"No se pudieron registrar signals: {e}")
        
        # 2. Cargar índices FAISS (rápido, <1s incluso en producción)
        # NOTA: En producción con PRODUCTION=true igual se cargan porque
        # son necesarios para búsquedas y pesan solo metadata en RAM.
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
            from .skills.matching_hybrid import HybridMatchingSkill
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
            # ── Skills del Sistema Experto Multi-Rol (SPEC v2.0) ──
            from .skills.nuevas import (
                MetricasGlobalesSkill,
                ReporteVentasSkill,
                AnalisisRendimientoSkill,
                ConsultarNormativaSkill,
                RevisarContratoSkill,
                AspectosLegalesSkill,
                CampanasActivasSkill,
                LeadsGeneradosSkill,
                MetricasMarketingSkill,
                MisPropiedadesSkill,
                MisRequerimientosSkill,
                MisMatchesSkill,
                PortafolioAgenteSkill,
                AnalizarOportunidadSkill,
                EquipoACargoSkill,
                DesempenoAgentesSkill,
                ReporteEquipoSkill,
                LogsSistemaSkill,
                ErroresRecientesSkill,
                EstadoServiciosSkill,
            )
            # ── Skills de Scraping de Portales (scrapi) ──
            from .skills.scrapi.scraper_remax import ScraperRemaxSkill
            from .skills.scrapi.scraper_adondevivir import ScraperAdondevivirSkill
            from .skills.scrapi.scraper_properati import ScraperProperatiSkill
            from .skills.scrapi.scraper_urbania import ScraperUrbaniaSkill
            from .skills.scrapi.scraper_orchestrator import ScraperOrchestratorSkill

            registry = SkillRegistry()
            registry.register(BusquedaPropiedadesSkill)
            registry.register(ACMAnalisisSkill)
            registry.register(ReportePreciosZonaSkill)
            registry.register(MatchingOfertaDemandaSkill)
            registry.register(HybridMatchingSkill)
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
            # ── Skills del Sistema Experto Multi-Rol (SPEC v2.0) ──
            registry.register(MetricasGlobalesSkill)
            registry.register(ReporteVentasSkill)
            registry.register(AnalisisRendimientoSkill)
            registry.register(ConsultarNormativaSkill)
            registry.register(RevisarContratoSkill)
            registry.register(AspectosLegalesSkill)
            registry.register(CampanasActivasSkill)
            registry.register(LeadsGeneradosSkill)
            registry.register(MetricasMarketingSkill)
            registry.register(MisPropiedadesSkill)
            registry.register(MisRequerimientosSkill)
            registry.register(MisMatchesSkill)
            registry.register(PortafolioAgenteSkill)
            registry.register(AnalizarOportunidadSkill)
            registry.register(EquipoACargoSkill)
            registry.register(DesempenoAgentesSkill)
            registry.register(ReporteEquipoSkill)
            registry.register(LogsSistemaSkill)
            registry.register(ErroresRecientesSkill)
            registry.register(EstadoServiciosSkill)
            # ── Skills de Scraping de Portales (scrapi) ──
            registry.register(ScraperRemaxSkill)
            registry.register(ScraperAdondevivirSkill)
            registry.register(ScraperProperatiSkill)
            registry.register(ScraperUrbaniaSkill)
            registry.register(ScraperOrchestratorSkill)
            logger.info(
                f"Skills registradas en SkillRegistry al iniciar Django "
                f"(incluye 20 nuevas skills multi-rol + 5 scrapi skills)"
            )
        except Exception as e:
            logger.warning(f"No se pudieron registrar skills en startup: {e}")

        # ── Registrar agentes en AgentRegistry ──
        try:
            from .agents.registry import AgentRegistry
            from .agents.propiedades_agent import AgentePropiedades
            from .agents.mercado_agent import AgenteMercado
            from .agents.requerimientos_agent import AgenteRequerimientos

            agent_registry = AgentRegistry()
            agent_registry.register(AgentePropiedades())
            agent_registry.register(AgenteMercado())
            agent_registry.register(AgenteRequerimientos())
            logger.info(
                f"3 agentes registrados en AgentRegistry: "
                f"propiedades, mercado, requerimientos"
            )
        except Exception as e:
            logger.warning(f"No se pudieron registrar agentes en startup: {e}")

        # 4. Pre-calcular embeddings del Semantic Router (F1-001)
        # NOTA: Solo se ejecuta en procesos NO saltados (i.e. no gunicorn ni collectstatic).
        # Esto evita que gunicorn workers carguen el modelo de embeddings (~1GB) en startup,
        # lo que causaba OOM/restart loop en Azure App Service.
        # El modelo se cargará lazy en la primera solicitud que requiera embeddings.
        if not _should_skip:
            try:
                from .services.semantic_router import precompute_router_embeddings
                n = precompute_router_embeddings()
                if n > 0:
                    logger.info(f"Semantic Router: {n} templates embeddeados para routing semántico")
            except Exception as e:
                logger.warning(f"No se pudieron pre-calcular embeddings del Semantic Router: {e}")

    def _preload_models(self):
        """
        Pre-carga el modelo de embeddings al iniciar Django.
        
        SPEC-014: Evita latencia de 10-20s en la primera consulta.
        Se ejecuta en el proceso principal de Django (RUN_MAIN=true).
        
        FIX-OOM: El modelo se saltó durante startup por gunicorn/collectstatic.
        Se carga lazy en la primera consulta real.
        
        Logs esperados:
            [INTEL] Pre-cargando modelo de embeddings: intfloat/multilingual-e5-small
            [INTEL] Sin GPU detectada — cargando modelo en CPU
            [INTEL] Modelo de embeddings inicializado (384 dimensiones, device=cpu, carga=~5000ms)
            [INTEL] Modelo de embeddings pre-cargado exitosamente
            [INTEL] Pre-cálculo de templates completado en 320ms (78 templates)
        """
        overall_start = time.time()
        logger.info("=== SPEC-014: Pre-carga de modelos de embeddings ===")

        # 5a. Pre-cargar modelo de embeddings
        model_loaded = False
        try:
            from .services.rag import RAGService
            model_loaded = RAGService.preload_embedder()
        except Exception as e:
            logger.warning(
                f"[SPEC-014] Error en pre-carga de modelo de embeddings: {e}. "
                f"Se cargará lazy en la primera consulta."
            )

        # 5b. Pre-calcular embeddings del Semantic Router
        templates_ok = 0
        try:
            from .services.semantic_router import precompute_router_embeddings
            templates_ok = precompute_router_embeddings()
        except Exception as e:
            logger.warning(
                f"[SPEC-014] Error en pre-cálculo de templates del router: {e}. "
                f"Se usarán keywords como fallback."
            )

        # Resumen final
        overall_elapsed = (time.time() - overall_start) * 1000
        logger.info(
            f"[SPEC-014] Resumen de pre-carga: "
            f"modelo={'✅' if model_loaded else '❌'} | "
            f"templates={templates_ok} | "
            f"tiempo_total={overall_elapsed:.0f}ms"
        )
        logger.info("=== SPEC-014: Fin de pre-carga ===")
