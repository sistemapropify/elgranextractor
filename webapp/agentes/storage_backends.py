"""
Storage backends personalizados para agentes app.

Usa containers separados de Azure Blob Storage para:
- logos_inmobiliarias/ → Container configurado en AZURE_LOGOS_CONTAINER
- iconos_marcadores/ → Container configurado en AZURE_ICONOS_CONTAINER
"""
from storages.backends.azure_storage import AzureStorage
from django.conf import settings


class LogoStorage(AzureStorage):
    """Storage para logos de inmobiliarias."""

    def __init__(self, *args, **kwargs):
        self.azure_container = settings.AZURE_LOGOS_CONTAINER
        super().__init__(*args, **kwargs)


class IconoMarcadorStorage(AzureStorage):
    """Storage para íconos de marcadores de mapa."""

    def __init__(self, *args, **kwargs):
        self.azure_container = settings.AZURE_ICONOS_CONTAINER
        super().__init__(*args, **kwargs)
