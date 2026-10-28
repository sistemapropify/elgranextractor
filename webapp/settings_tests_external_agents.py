"""Aislamiento local para probar el módulo de agentes externos.

La base de producción no se usa. Las migraciones históricas de otras apps
no son compatibles con SQLite, por lo que este settings crea el esquema desde
los modelos actuales únicamente para ejecutar pruebas automatizadas.
"""

import os


_ACTIVE_SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE')
os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings'
from test_settings import *  # noqa: E402,F403,F401
os.environ['DJANGO_SETTINGS_MODULE'] = (
    _ACTIVE_SETTINGS_MODULE or 'settings_tests_external_agents'
)


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
TEST_RUNNER = 'external_agents.test_runner.ExternalAgentsTestRunner'
