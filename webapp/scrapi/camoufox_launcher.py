"""Configuracion comun para lanzar Camoufox en local y produccion."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path


_DEFAULTS = {"os": "windows", "humanize": True}
_FETCH_TIMEOUT = int(os.environ.get("CAMOUFOX_FETCH_TIMEOUT", "180"))
_STALE_LOCK = int(os.environ.get("CAMOUFOX_STALE_LOCK_SECONDS", "120"))


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


def _boot_id() -> str:
    try:
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        return ''


def _lock_owner_alive(lock: Path) -> bool:
    """Comprueba si el instalador que creó el lock sigue vivo."""
    owner_file = lock / 'owner.json'
    try:
        owner = json.loads(owner_file.read_text(encoding='utf-8'))
        pid = int(owner.get('pid', 0))
        owner_boot = str(owner.get('boot_id', ''))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    if owner_boot and _boot_id() and owner_boot != _boot_id():
        return False
    try:
        os.kill(pid, 0)
        return pid > 0
    except (OSError, ValueError):
        return False


def _remove_install_lock(lock: Path) -> None:
    try:
        (lock / 'owner.json').unlink(missing_ok=True)
        lock.rmdir()
    except OSError:
        pass

def _notify(progress_callback, message: str) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(message)
    except Exception:
        pass


def ensure_camoufox_installed(progress_callback=None) -> Path:
    """Instala el browser con la API que Camoufox usa internamente.

    No se pasa ``data_dir``: ese argumento no existe ni en ``AsyncCamoufox``
    ni en el CLI actual. La ruta se controla mediante ``XDG_CACHE_HOME`` antes
    de que el proceso Python arranque.
    """
    installed = _installed_path()
    if installed is not None:
        _notify(progress_callback, f'Camoufox: navegador encontrado en {installed}')
        return installed

    install_dir = get_install_dir()
    install_dir.mkdir(parents=True, exist_ok=True)
    lock = install_dir / ".propifai-fetch.lock"
    started = time.monotonic()
    owns_lock = False

    while True:
        try:
            lock.mkdir()
            (lock / 'owner.json').write_text(
                json.dumps({'pid': os.getpid(), 'boot_id': _boot_id()}),
                encoding='utf-8',
            )
            owns_lock = True
            break
        except FileExistsError:
            installed = _installed_path()
            if installed is not None:
                return installed
            try:
                lock_age = time.time() - lock.stat().st_mtime
            except OSError:
                lock_age = 0
            owner_file = lock / 'owner.json'
            dead_owner = owner_file.exists() and not _lock_owner_alive(lock)
            legacy_stale = (
                not owner_file.exists() and lock_age >= min(_STALE_LOCK, 5)
            )
            if dead_owner or legacy_stale:
                _remove_install_lock(lock)
                continue
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

        _notify(
            progress_callback,
            f'Camoufox: descargando navegador en {install_dir} '
            f'(límite {_FETCH_TIMEOUT}s)',
        )
        completed = subprocess.run(
            [sys.executable, '-m', 'camoufox', 'fetch'],
            capture_output=True,
            text=True,
            timeout=_FETCH_TIMEOUT,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or '').strip()[-1000:]
            raise RuntimeError(
                f'camoufox fetch terminó con código {completed.returncode}: {detail}'
            )
        installed = _installed_path()
        if installed is None:
            raise RuntimeError('camoufox fetch terminó sin registrar un navegador activo')
        if not installed.exists():
            raise RuntimeError(f"Camoufox devolvio una ruta inexistente: {installed}")
        _notify(progress_callback, f'Camoufox: descarga completada en {installed}')
        return installed
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f'La descarga de Camoufox excedió el límite de {_FETCH_TIMEOUT} segundos.'
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "No se pudo instalar el navegador Camoufox en el servidor "
            f"({install_dir}): {exc}"
        ) from exc
    finally:
        if owns_lock:
            _remove_install_lock(lock)


class CamoufoxSystemDependencyError(RuntimeError):
    """El host Linux no tiene las bibliotecas nativas de Camoufox."""


_CAMOUFOX_DEPS_INSTALLING = Path('/tmp/propifai-camoufox-deps.installing')
_CAMOUFOX_DEPS_WAIT_SECONDS = int(
    os.environ.get('CAMOUFOX_DEPS_WAIT_SECONDS', '360')
)


def _missing_camoufox_dependencies() -> list[str]:
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
    return missing


def ensure_camoufox_system_dependencies(progress_callback=None) -> None:
    """Espera la instalacion de startup y valida las librerias nativas."""
    if not is_headless_server():
        return

    missing = _missing_camoufox_dependencies()
    if missing and _CAMOUFOX_DEPS_INSTALLING.exists():
        deadline = time.monotonic() + _CAMOUFOX_DEPS_WAIT_SECONDS
        while missing and time.monotonic() < deadline:
            time.sleep(2)
            missing = _missing_camoufox_dependencies()
            if not _CAMOUFOX_DEPS_INSTALLING.exists() and missing:
                break

    if missing:
        raise CamoufoxSystemDependencyError(
            'Camoufox no puede iniciar: faltan dependencias Linux: '
            + ', '.join(missing)
            + '. Revise /home/LogFiles/camoufox-deps.log.'
        )

def camoufox_kwargs(**overrides) -> dict:
    """Prepara el browser y devuelve opciones validas para AsyncCamoufox."""
    progress_callback = overrides.pop('_progress_callback', None)
    ensure_camoufox_system_dependencies(progress_callback)
    ensure_camoufox_installed(progress_callback)
    kwargs = dict(_DEFAULTS, headless=is_headless_server())
    kwargs.update(overrides)
    return kwargs
