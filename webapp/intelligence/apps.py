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
