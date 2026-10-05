"""Wait for the person to use the actual local browser, never replay a click."""
import asyncio
import time

from .browser_verification import allowed_page, content_ready
from .contracts import ScrapingInterrupted


async def resolve_native(page, emit, timeout=300):
    if not allowed_page(page):
        raise ScrapingInterrupted('Dominio inesperado en la verificación local.')
    await page.bring_to_front()
    await emit(event='verification.local_required', level='warning',
               message='Resuelve la verificación directamente en la ventana de Camoufox de tu PC. '
                       'No uses la imagen del dashboard. Se espera hasta 5 minutos sin recargar.')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Poll the job's pause/stop/ownership through the normal callback.
        # No screenshot or generated input is involved.
        await emit(event='verification.local_waiting', level='debug')
        if not allowed_page(page):
            raise ScrapingInterrupted('Dominio inesperado en la verificación local.')
        if await content_ready(page):
            await emit(event='verification.completed',
                       message='El navegador local recibió el listado; continúa la lectura.')
            return True
        await asyncio.sleep(1)
    raise ScrapingInterrupted('portal.paused: el portal no confirmó acceso en la ventana local; pendientes conservados.')
