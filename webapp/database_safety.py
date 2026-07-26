"""Guardas para impedir el uso accidental de otras bases en Azure SQL."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any


PRODUCTION_DATABASE_NAME = "propiextractor"
AZURE_SQL_HOST_SUFFIX = ".database.windows.net"
FORBIDDEN_DATABASE_NAMES = {":memory:", "memory", "dummy"}


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def validate_database_safety(
    databases: Mapping[str, Mapping[str, Any]],
    argv: list[str] | None = None,
    *,
    allow_local_test_settings: bool = False,
) -> None:
    """Falla antes de conectar si una configuración puede crear otra BD."""

    command_line = list(sys.argv if argv is None else argv)

    for alias, config in databases.items():
        engine = _normalized(config.get("ENGINE"))
        host = _normalized(config.get("HOST"))
        name = _normalized(config.get("NAME"))
        is_azure_sql = host.endswith(AZURE_SQL_HOST_SUFFIX)

        if not is_azure_sql:
            continue

        if name in FORBIDDEN_DATABASE_NAMES or name.startswith("test_"):
            raise RuntimeError(
                f"Base prohibida para '{alias}': {config.get('NAME')!r}. "
                f"Azure SQL solo puede usar {PRODUCTION_DATABASE_NAME!r}."
            )

        if alias == "default" and name != PRODUCTION_DATABASE_NAME:
            raise RuntimeError(
                "DB_NAME inválido para Azure SQL. La conexión principal debe "
                f"apuntar exclusivamente a {PRODUCTION_DATABASE_NAME!r}; "
                f"se recibió {config.get('NAME')!r}."
            )

        if (
            "mssql" in engine
            and "test" in command_line
            and not allow_local_test_settings
        ):
            raise RuntimeError(
                "Está prohibido ejecutar tests de Django contra Azure SQL. "
                "Use los settings locales de prueba."
            )
