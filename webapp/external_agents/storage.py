from django.conf import settings
from storages.backends.azure_storage import AzureStorage


class ExternalAgentDocumentStorage(AzureStorage):
    """Almacenamiento privado para los adjuntos de agentes externos."""

    def __init__(self, *args, **kwargs):
        self.azure_container = getattr(
            settings,
            'AZURE_EXTERNAL_AGENTS_CONTAINER',
            'documentos-agentes-externos',
        )
        super().__init__(*args, **kwargs)
