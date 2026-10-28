from pathlib import Path

from django.test.runner import DiscoverRunner


class ExternalAgentsTestRunner(DiscoverRunner):
    """Evita que la etiqueta quede resuelta como ``webapp.external_agents``."""

    def __init__(self, *args, **kwargs):
        if not kwargs.get('top_level'):
            kwargs['top_level'] = str(Path(__file__).resolve().parents[1])
        super().__init__(*args, **kwargs)
