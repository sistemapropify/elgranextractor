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

INSTALACIÓN DEL BINARIO (importante en producción)
--------------------------------------------------
``pip install camoufox`` solo instala el paquete Python; el binario del
navegador (un Firefox modificado) se descarga aparte con ``camoufox fetch``.
En Azure App Service esto NO ocurre automáticamente, por eso el scraper falla
en producción con:

    official/stable is not installed. Please run `camoufox fetch` to install.

Aquí se resuelve de forma transparente: ``camoufox_kwargs()`` (que todos los
scrapers llaman justo antes de lanzar el navegador) se asegura de que el
binario esté descargado antes de devolver los kwargs.

El binario se guarda en un ``data_dir`` persistente:

1. Si existe la variable de entorno ``CAMOUFOX_DATA_DIR`` se usa esa ruta.
   Recomendado en Azure App Service apuntando a ``/home/...`` para que
   sobreviva reinicios y despliegues (p.ej. ``/home/camoufox-data``).
2. Si no, se usa el directorio de datos de la plataforma (``platformdirs``),
   que en el App Service Linux (con ``HOME=/home``) es
   ``/home/.local/share/camoufox`` y también persiste entre reinicios.
"""

import os
import subprocess
import sys
import time

try:
    import platformdirs
except ImportError:  # pragma: no cover - suele venir como dependencia de camoufox
    platformdirs = None

# Parámetros base comunes a todos los scrapers.
_DEFAULTS = {
    'os': 'windows',
    'humanize': True,
}

# Canal por defecto de Camoufox (el mismo que usa `camoufox fetch`).
_CANAL = 'stable'

# Tiempo máximo de espera por el lock de descarga / por la propia descarga.
_TIMEOUT_FETCH = 900  # segundos (15 min; la primera descarga es pesada)
# Un lock más viejo que esto se considera huérfano (descarga previa murió).
_LOCK_STALE = 1800    # segundos


def get_data_dir() -> str:
    """Directorio persistente donde vive el binario de Camoufox.

    Prioridad:
    1. Variable de entorno ``CAMOUFOX_DATA_DIR`` (recomendada en Azure
       App Service, p.ej. ``/home/camoufox-data``).
    2. Directorio de datos de la plataforma (``platformdirs``). En el App
       Service Linux con ``HOME=/home`` es ``/home/.local/share/camoufox``,
       que persiste entre reinicios y despliegues.
    """
    override = os.environ.get('CAMOUFOX_DATA_DIR')
    if override:
        return override
    if platformdirs is not None:
        return platformdirs.user_data_dir('camoufox')
    # Fallback portable si no hay platformdirs.
    base = os.path.expanduser('~')
    if sys.platform.startswith('linux'):
        return os.path.join(base, '.local', 'share', 'camoufox')
    if sys.platform == 'darwin':
        return os.path.join(base, 'Library', 'Application Support', 'camoufox')
    return os.path.join(os.environ.get('LOCALAPPDATA', base), 'camoufox')


def _camoufox_instalado(data_dir: str) -> bool:
    """True si el binario de Camoufox ya está disponible en ``data_dir``."""
    try:
        from camoufox.pkgman import installed
        return bool(installed(data_dir))
    except Exception:
        # Si no se puede inspeccionar, asumimos que NO está instalado para
        # intentar la descarga.
        return False


def _fetch_binario(data_dir: str) -> bool:
    """Descarga el binario de Camoufox (API oficial, con fallback a CLI)."""
    try:
        from camoufox.pkgman import fetch
        fetch(data_dir)
        return _camoufox_instalado(data_dir)
    except Exception as exc_api:
        try:
            subprocess.run(
                [sys.executable, '-m', 'camoufox', '--data-dir', data_dir, 'fetch'],
                check=True,
                timeout=_TIMEOUT_FETCH,
            )
            return _camoufox_instalado(data_dir)
        except Exception as exc_cli:
            print(
                f"[camoufox] No se pudo descargar el binario "
                f"(API: {exc_api}; CLI: {exc_cli})"
            )
            return False


def ensure_camoufox_installed(data_dir: str | None = None) -> str:
    """Garantiza que el binario de Camoufox esté descargado en ``data_dir``.

    Se llama desde ``camoufox_kwargs()`` justo antes de lanzar el navegador.
    Usa un lock de directorio (atómico) para evitar descargas concurrentes
    cuando varios workers (web + celery) arrancan a la vez.

    Devuelve el ``data_dir`` listo para usar. Lanza ``RuntimeError`` con un
    mensaje claro si la descarga falla, en lugar del críptico mensaje
    "official/stable is not installed".
    """
    data_dir = data_dir or get_data_dir()
    if _camoufox_instalado(data_dir):
        return data_dir

    os.makedirs(data_dir, exist_ok=True)
    lock = os.path.join(data_dir, '.fetch.lock')
    inicio = time.monotonic()
    tengo_lock = False

    # Intentar adquirir el lock de forma atómica (os.mkdir es atómico).
    while True:
        try:
            os.mkdir(lock)
            tengo_lock = True
            break
        except FileExistsError:
            # Detectar lock huérfano (una descarga previa murió a medias).
            try:
                if time.time() - os.path.getmtime(lock) > _LOCK_STALE:
                    os.rmdir(lock)
                    continue
            except OSError:
                pass
            if time.monotonic() - inicio > _TIMEOUT_FETCH:
                raise RuntimeError(
                    f"Camoufox no instalado y otro proceso lleva más de "
                    f"{_TIMEOUT_FETCH}s descargándolo en {data_dir}. "
                    f"Reintente el scraping más tarde."
                )
            time.sleep(2)
        except OSError:
            # Sin permisos para crear el lock: descargar igualmente.
            tengo_lock = True
            break

    try:
        print(f"⚙️  Camoufox no encontrado en {data_dir}; descargando binario...")
        ok = _fetch_binario(data_dir)
    finally:
        if tengo_lock:
            try:
                os.rmdir(lock)
            except OSError:
                pass

    if not ok:
        raise RuntimeError(
            "Camoufox no está instalado en este servidor. Ejecute manualmente "
            f"`camoufox fetch` (o `python -m camoufox --data-dir {data_dir} fetch`) "
            "desde la consola/Kudu del App Service, o revise la red y los "
            "permisos del entorno."
        )
    return data_dir


def is_headless_server() -> bool:
    """True si corremos en un servidor Linux sin pantalla (producción)."""
    return sys.platform.startswith('linux')


def camoufox_kwargs(**overrides) -> dict:
    """Retorna kwargs para ``AsyncCamoufox`` según la plataforma.

    - Linux (servidor de producción, sin display): headless=True.
    - Windows/macOS (desarrollo local con pantalla): headless=False, para
      permitir resolución manual de captchas.

    Además garantiza que el binario de Camoufox esté descargado (ver
    ``ensure_camoufox_installed``), de modo que los scrapers funcionen en
    producción sin necesidad de ejecutar ``camoufox fetch`` manualmente.

    Cualquier parámetro adicional (p.ej. ``persistent_context``,
    ``user_data_dir``) se pasa como keyword argument y se fusiona encima de
    los valores por defecto.
    """
    kwargs = dict(_DEFAULTS, headless=is_headless_server())
    # El data_dir del binario se puede forzar con CAMOUFOX_DATA_DIR.
    kwargs.setdefault('data_dir', get_data_dir())
    kwargs.update(overrides)
    # Descargar el binario si hace falta ANTES de devolver los kwargs.
    ensure_camoufox_installed(kwargs['data_dir'])
    return kwargs
