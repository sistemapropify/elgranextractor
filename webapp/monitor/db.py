"""Acceso de SOLO LECTURA a la base de Propify (``dbpropify_be``).

Esa base no se modifica nunca: es la base de negocio de Propify y este modulo es
la unica puerta de entrada del monitoreo. Toda consulta pasa por ``_validar()``,
que rechaza cualquier sentencia que no sea de lectura.

La validacion es una red de seguridad, no la proteccion definitiva: lo realmente
solido es que el usuario de base de datos del monitoreo tenga permiso de solo
lectura. Mientras siga siendo el usuario administrador, esta capa es lo que
impide un descuido.
"""
from __future__ import annotations

import re

from django.db import connections

ALIAS = 'propifai'

_SOLO_LECTURA = re.compile(r'^\s*(?:select|with)\b', re.IGNORECASE)

# Palabras que delatan una escritura aunque la sentencia empiece con SELECT o
# WITH: "SELECT ... INTO tabla", "WITH x AS (...) DELETE FROM ...", etc.
_ESCRITURA = re.compile(
    r'\b(?:insert|update|delete|drop|alter|create|truncate|merge|grant|revoke'
    r'|exec|execute|into|sp_|xp_)\b',
    re.IGNORECASE,
)


class EscrituraBloqueada(Exception):
    """Se intento ejecutar algo que no es una consulta de lectura."""


def _validar(sql: str) -> None:
    if not _SOLO_LECTURA.match(sql or ''):
        raise EscrituraBloqueada('dbpropify_be es de solo lectura: se esperaba SELECT o WITH.')
    encontrado = _ESCRITURA.search(sql)
    if encontrado:
        raise EscrituraBloqueada(
            f'dbpropify_be es de solo lectura: la consulta contiene «{encontrado.group(0)}».'
        )


def consultar(sql: str, parametros=None):
    """Ejecuta una consulta de lectura y devuelve ``(columnas, filas)``."""
    _validar(sql)
    with connections[ALIAS].cursor() as cursor:
        cursor.execute(sql, list(parametros or []))
        columnas = [c[0] for c in cursor.description] if cursor.description else []
        return columnas, cursor.fetchall()


def filas(sql: str, parametros=None):
    """Igual que ``consultar`` pero devuelve solo las filas."""
    return consultar(sql, parametros)[1]


def disponible() -> tuple[bool, str]:
    """Comprueba si la base responde. Devuelve ``(ok, detalle)`` sin levantar."""
    try:
        consultar('SELECT 1 AS ok')
        return True, ''
    except EscrituraBloqueada:
        raise
    except Exception as exc:  # red, firewall, permisos, driver
        return False, str(exc)[:300]
