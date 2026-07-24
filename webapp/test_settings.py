"""
Settings de prueba para Django — SOBREESCRIBE las bases de datos Azure SQL
con SQLite en memoria para EVITAR crear bases de datos test_ en Azure.

Uso:
    python manage.py test --settings=webapp.test_settings

¿Por qué existe este archivo?
    Django automáticamente crea bases de datos con prefijo "test_" en el
    servidor configurado cuando ejecutas 'python manage.py test' con
    TestCase. En producción con Azure SQL, esto genera:
      - Bases de datos test_ en Azure SQL (costo adicional ~$100 USD)
      - Riesgo de seguridad (datos de prueba en servidor productivo)

    Este settings overrides las conexiones a bases de datos para que los
    tests corran localmente con SQLite, sin afectar Azure.
"""

from __future__ import annotations

from .settings import *  # noqa: F403, F401 — heredar TODO del settings principal

# ── SOBREESCRIBIR BASES DE DATOS PARA EVITAR Azure SQL ──────────────
# Django crea automáticamente test_PREFIX + DB_NAME en el servidor configurado
# cuando se ejecutan tests. Con mssql apuntando a Azure SQL, esto genera
# bases de datos test_ en Azure facturables.
#
# SOLUCIÓN: Usar SQLite en memoria para los tests.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {
            'NAME': ':memory:',
        },
    },
    'propifai': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {
            'NAME': ':memory:',
        },
    },
}

# ── DESACTIVAR DATABASE ROUTERS ────────────────────────────────────
# Los routers apuntan a servidores Azure SQL que ya no estamos usando en tests.
DATABASE_ROUTERS = []

# ── SEGURO CONTRA EJECUCIÓN ACCIDENTAL EN PRODUCCIÓN ──────────────
# Si por error se intenta usar este settings apuntando a Azure, cancelar.
import os
import sys

if 'test' not in sys.argv:
    raise RuntimeError(
        "⛔ test_settings.py solo debe usarse para ejecutar tests.\n"
        "    Uso correcto: python manage.py test --settings=webapp.test_settings\n"
        "    Para correr el servidor usa el settings normal (webapp.settings)."
    )
