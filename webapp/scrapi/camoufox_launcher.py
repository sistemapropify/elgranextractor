"""Configuracion comun para lanzar Camoufox en local y produccion."""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path


_DEFAULTS = {"os": "windows", "humanize": True}
_FETCH_TIMEOUT = 900
_STALE_LOCK = 1800


def is_headless_server() -> bool:
    """True cuando se ejecuta en un servidor Linux sin pantalla."""
    return sys.platform.startswith("linux")


def get_install_dir() -> Path:
    """Devuelve la ruta que la version instalada de Camoufox usa realmente.

    Camoufox usa ``platformdirs.user_cache_dir('camoufox')``. En Azure,
    ``startup.sh`` fija ``XDG_CACHE_HOME=/home/.cache`` antes de importar
    Python para que el navegador quede en almacenamiento persistente.
    """
    from camoufox.pkgman import INSTALL_DIR

    return Path(INSTALL_DIR)


def _installed_path() -> Path | None:
    """Obtiene el browser activo sin iniciar una descarga."""
    try:
        from camoufox.pkgman import camoufox_path

        return Path(camoufox_path(download_if_missing=False))
    except Exception:
        return None


def ensure_camoufox_installed() -> Path:
    """Instala el browser con la API que Camoufox usa internamente.

    No se pasa ``data_dir``: ese argumento no existe ni en ``AsyncCamoufox``
    ni en el CLI actual. La ruta se controla mediante ``XDG_CACHE_HOME`` antes
    de que el proceso Python arranque.
    """
    installed = _installed_path()
    if installed is not None:
        return installed

    install_dir = get_install_dir()
    install_dir.mkdir(parents=True, exist_ok=True)
    lock = install_dir / ".propifai-fetch.lock"
    started = time.monotonic()
    owns_lock = False

    while True:
        try:
            lock.mkdir()
            owns_lock = True
            break
        except FileExistsError:
            installed = _installed_path()
            if installed is not None:
                return installed
            try:
                if time.time() - lock.stat().st_mtime > _STALE_LOCK:
                    lock.rmdir()
                    continue
            except OSError:
                pass
            if time.monotonic() - started >= _FETCH_TIMEOUT:
                raise RuntimeError(
                    "Camoufox no termino de instalarse dentro de "
                    f"{_FETCH_TIMEOUT} segundos en {install_dir}."
                )
            time.sleep(2)

    try:
        # Otro proceso pudo completar la descarga justo antes de tomar el lock.
        installed = _installed_path()
        if installed is not None:
            return installed

        print(f"[camoufox] Descargando navegador en {install_dir}...")
        from camoufox.pkgman import camoufox_path

        installed = Path(camoufox_path(download_if_missing=True))
        if not installed.exists():
            raise RuntimeError(f"Camoufox devolvio una ruta inexistente: {installed}")
        return installed
    except Exception as exc:
        raise RuntimeError(
            "No se pudo instalar el navegador Camoufox en el servidor "
            f"({install_dir}): {exc}"
        ) from exc
    finally:
        if owns_lock:
            try:
                lock.rmdir()
            except OSError:
                pass


class CamoufoxSystemDependencyError(RuntimeError):
    """El host Linux no tiene las bibliotecas nativas de Camoufox."""


def ensure_camoufox_system_dependencies() -> None:
    """Valida las librerías del navegador antes de intentar lanzarlo."""
    if not is_headless_server():
        return

    required = (
        ('libgtk-3.so.0', 'libgtk-3-0/libgtk-3-0t64'),
        ('libX11-xcb.so.1', 'libx11-xcb1'),
        ('libasound.so.2', 'libasound2/libasound2t64'),
    )
    missing = []
    for library, package in required:
        try:
            ctypes.CDLL(library)
        except OSError:
            missing.append(f'{library} ({package})')

    if missing:
        raise CamoufoxSystemDependencyError(
            'Camoufox no puede iniciar: faltan dependencias Linux: '
            + ', '.join(missing)
            + '. Revise la etapa [2/6] del startup de Azure.'
        )


def camoufox_kwargs(**overrides) -> dict:
    """Prepara el browser y devuelve opciones validas para AsyncCamoufox."""
    ensure_camoufox_installed()
    ensure_camoufox_system_dependencies()
    kwargs = dict(_DEFAULTS, headless=is_headless_server())
    kwargs.update(overrides)
    return kwargs
