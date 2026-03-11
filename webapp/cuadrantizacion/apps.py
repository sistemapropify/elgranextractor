from django.apps import AppConfig


class CuadrantizacionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cuadrantizacion'
    verbose_name = "Cuadrantización Inmobiliaria"
    
    def ready(self):
        # Importar señales si es necesario
        # import cuadrantizacion.signals  # noqa
        pass