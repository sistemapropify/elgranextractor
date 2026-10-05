"""Human-only interaction with an Adondevivir challenge in the worker's session.

No automatic solver, reload loop, cookie export or external navigation control.
"""
import asyncio
import base64
import re
import time
from urllib.parse import urlsplit
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout

from .contracts import ScrapingInterrupted

WIDTH, HEIGHT = 1440, 1000


def parse_action(value):
    if value == 'refresh':
        return ('refresh',)
    if not isinstance(value, str):
        raise ValueError('Acción de verificación inválida.')
    match = re.fullmatch(r'c:([0-9]{1,4}):([0-9]{1,4})', value)
    if match and int(match[1]) < WIDTH and int(match[2]) < HEIGHT:
        return ('click', int(match[1]), int(match[2]))
    raise ValueError('El clic debe estar dentro de la pantalla de verificación.')


def allowed_page(page):
    parsed = urlsplit(page.url)
    return parsed.scheme == 'https' and parsed.hostname in ('www.adondevivir.com', 'adondevivir.com')


async def _content_ready(page):
    if not allowed_page(page):
        return False
    title = (await page.title()).lower()
    if any(x in title for x in ('just a moment', 'access denied', 'attention required', 'captcha', 'forbidden')):
        return False
    # A title change alone does not establish that a listing/detail was served.
    return bool(await page.locator(
        '[data-to-posting], [data-qa="POSTING_CARD_PRICE"], #postingDescription, '
        '[data-qa="POSTING_DESCRIPTION"], .title-type-sup-property'
    ).count()) and getattr(page, '_scraping_document_status', 200) not in (403, 429)


async def content_ready(page):
    try:
        return await _content_ready(page)
    except Exception:
        # Navigation can destroy the document between title and DOM reads.
        return False


async def resolve(page, exchange, emit, timeout=300):
    if not allowed_page(page):
        raise ScrapingInterrupted('portal.paused: Adondevivir cambió de dominio; pendientes conservados')
    deadline = time.monotonic() + min(timeout, 300)
    await emit(event='verification.required', level='warning',
               message='Adondevivir requiere verificación: abre la pantalla en el dashboard y responde allí. '
                       'Se mantiene el navegador de producción durante 5 minutos.')
    try:
        # Listing and detail share a context but are separate tabs. The human
        # must interact with the tab represented by this screenshot.
        await page.bring_to_front()
        await page.set_viewport_size({'width': WIDTH, 'height': HEIGHT})
        screenshot_failures = 0
        while time.monotonic() < deadline:
            if await content_ready(page):
                await emit(event='verification.completed', message='Adondevivir confirmó acceso; continúa la extracción.')
                return True
            if not allowed_page(page):
                break
            try:
                screenshot = await page.screenshot(
                    type='png', full_page=False, scale='css',
                    timeout=max(1, min(10000, int((deadline - time.monotonic()) * 1000))))
            except BrowserTimeout as exc:
                screenshot_failures += 1
                await emit(event='verification.screenshot_failed', level='warning',
                           message=f'La captura de verificación agotó su tiempo ({screenshot_failures}/3). '
                                   'Se conserva la misma pestaña, sin recargar el portal.')
                if screenshot_failures >= 3:
                    raise ScrapingInterrupted(
                        'portal.paused: el navegador no pudo capturar la verificación tras 3 intentos; '
                        'no se recargará el portal; pendientes conservados') from exc
                await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
                continue
            screenshot_failures = 0
            challenge_id = await asyncio.to_thread(exchange, 'open',
                screenshot=base64.b64encode(screenshot).decode('ascii'),
                seconds=max(1, int(deadline-time.monotonic())))
            # Keep each screenshot ID stable until a human acts. Refreshing uses
            # a new ID, so a delayed click cannot act on a later screen.
            while time.monotonic() < deadline:
                answer = await asyncio.to_thread(exchange, 'poll', id=challenge_id)
                if await content_ready(page):
                    await emit(event='verification.completed', message='Adondevivir confirmó acceso; continúa la extracción.')
                    return True
                if not allowed_page(page):
                    raise ScrapingInterrupted('portal.paused: dominio de verificación inesperado; pendientes conservados')
                if answer is not None:
                    action = parse_action(answer)
                    if action[0] == 'click':
                        # Forward only the coordinates submitted by the user.
                        await page.bring_to_front()
                        await page.mouse.click(action[1], action[2])
                        await asyncio.to_thread(exchange, 'executed', id=challenge_id)
                        await emit(event='verification.click_executed',
                                   message='El navegador ejecutó tu clic. Esto no confirma aún el acceso de Adondevivir.')
                    await asyncio.sleep(1)
                    break
                await asyncio.sleep(1)
        raise ScrapingInterrupted('portal.paused: Adondevivir no confirmó la verificación; pendientes conservados')
    except BrowserError as exc:
        # A broken verification browser is not a transient listing request.
        # Letting this escape as a navigation error restarts the challenge.
        raise ScrapingInterrupted(
            'portal.paused: falló el navegador durante la verificación; '
            'no se recargará el portal; pendientes conservados') from exc
    finally:
        await asyncio.to_thread(exchange, 'close')
