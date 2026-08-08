"""Runner de test sin base de datos.

El proyecto usa Azure SQL de producción como BD ``default`` y el validador
``database_safety`` prohíbe bases ``test_*``. Este runner ejecuta SOLO tests que
no tocan la BD (SimpleTestCase) sin crear ni conectar a ninguna base de datos.

``top_level`` se fija a la carpeta ``webapp`` para que las etiquetas de test se
resuelvan como ``response_intelligence.tests`` (y no como ``webapp.response_intelligence``,
lo que rompería la resolución de ``app_label`` porque ``webapp/__init__.py`` hace
de ``webapp`` un paquete).
"""

import os

from django.test.runner import DiscoverRunner

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))


class NoDbTestRunner(DiscoverRunner):
    """DiscoverRunner que no configura ni crea bases de datos de test."""

    databases = set()

    def __init__(self, *args, **kwargs):
        # ``DiscoverRunner.__init__`` fija ``self.top_level = None`` por defecto y
        # pisaría el atributo de clase. ``manage.py test`` además pasa ``top_level=None``
        # explícitamente en las opciones, así que hay que reemplazar el ``None``, no
        # solo hacer ``setdefault``. Lo forzamos a la carpeta ``webapp`` para que las
        # etiquetas se resuelvan como ``response_intelligence.*`` y no como
        # ``webapp.response_intelligence.*`` (rompe la resolución de ``app_label``).
        if not kwargs.get("top_level"):
            kwargs["top_level"] = WEBAPP_DIR
        super().__init__(*args, **kwargs)
