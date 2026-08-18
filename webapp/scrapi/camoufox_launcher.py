"""
camoufox_launcher.py — Configuración de lanzamiento de Camoufox según la plataforma.

PROBLEMA
--------
Los scrapers se desarrollaron con ``headless=False`` (navegador visible) para
poder resolver captchas de Cloudflare manualmente en Windows. Pero en
producción (Azure App Service Linux) NO hay pantalla (servidor headless), así
que abrir un navegador visible falla con "cannot open display".

SOLUCIÓN
--------
- En Linux (servidor de producción sin pantalla) → headless=True.
- En Windows/macOS (desarrollo local con pantalla) → headless=False, para
  seguir permitiendo resolución manual de captchas.

Se conservan ``os='windows'`` y ``humanize=True`` en ambas plataformas para
mantener los mismos fingerprints con los que se calibraron los scrapers.
"""

import sys

# Parámetros base comunes a todos los scrapers.
_DEFAULTS = {
    'os': 'windows',
    'humanize': True,
}


def is_headless_server() -> bool:
    """True si corremos en un servidor Linux sin pantalla (producción)."""
    return sys.platform.startswith('linux')


def camoufox_kwargs(**overrides) -> dict:
    """Retorna kwargs para ``AsyncCamoufox`` según la plataforma.

    - Linux (servidor de producción, sin display): headless=True.
    - Windows/macOS (desarrollo local con pantalla): headless=False, para
      permitir resolución manual de captchas.

    Cualquier parámetro adicional (p.ej. ``persistent_context``,
    ``user_data_dir``) se pasa como keyword argument y se fusiona encima de
    los valores por defecto.
    """
    kwargs = dict(_DEFAULTS, headless=is_headless_server())
    kwargs.update(overrides)
    return kwargs
