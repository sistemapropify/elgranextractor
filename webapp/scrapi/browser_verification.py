"""Human-only interaction with an Adondevivir challenge in the worker's session.

No automatic solver, reload loop, cookie export or external navigation control.
"""
import asyncio
import base64
import re
import struct
import time
from urllib.parse import urlsplit
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout

from .contracts import ScrapingInterrupted

WIDTH, HEIGHT = 1440, 1000
MAX_SCREEN_COORDINATE = 8191
POST_CLICK_WAIT_SECONDS = 10


def parse_action(value):
    if value == 'refresh':
        return ('refresh',)
    if not isinstance(value, str):
        raise ValueError('Acción de verificación inválida.')
    match = re.fullmatch(r'c:([0-9]{1,4}):([0-9]{1,4})', value)
    if (match and int(match[1]) <= MAX_SCREEN_COORDINATE
            and int(match[2]) <= MAX_SCREEN_COORDINATE):
        return ('click', int(match[1]), int(match[2]))
    raise ValueError('El clic debe estar dentro de la pantalla de verificación.')


def _png_size(screenshot):
    """Read PNG dimensions without adding an image-processing dependency."""
    if len(screenshot) < 24 or screenshot[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    width, height = struct.unpack('>II', screenshot[16:24])
    if not width or not height:
        return None
    return {'width': width, 'height': height}


async def _viewport(page):
    """Return the CSS coordinate space that page.mouse uses."""
    try:
        result = await page.evaluate('''() => ({
            width: window.innerWidth,
            height: window.innerHeight,
            devicePixelRatio: window.devicePixelRatio,
            scrollX: window.scrollX,
            scrollY: window.scrollY
        })''')
        if result.get('width') and result.get('height'):
            return result
    except Exception:
        pass
    size = getattr(page, 'viewport_size', None) or {'width': WIDTH, 'height': HEIGHT}
    return {'width': size['width'], 'height': size['height'],
            'devicePixelRatio': None, 'scrollX': None, 'scrollY': None}


def _map_click(x, y, screenshot_size, viewport):
    """Map screenshot pixels to the current CSS viewport used by Playwright."""
    source = screenshot_size or {'width': WIDTH, 'height': HEIGHT}
    if x >= source['width'] or y >= source['height']:
        raise ValueError('El clic quedó fuera de la captura publicada.')
    mapped_x = min(viewport['width'] - 1, max(0, x * viewport['width'] / source['width']))
    mapped_y = min(viewport['height'] - 1, max(0, y * viewport['height'] / source['height']))
    return round(mapped_x, 2), round(mapped_y, 2)


async def _hit_target(page, x, y):
    """Describe the DOM node at a user-selected point; never searches for a challenge."""
    try:
        describe = '''([x, y]) => {
            const element = document.elementFromPoint(x, y);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            const value = text => String(text || '').slice(0, 160);
            return {
                tag: element.tagName.toLowerCase(),
                id: value(element.id),
                className: value(element.className),
                title: value(element.title),
                src: value(element.getAttribute('src')),
                rect: {x: Math.round(rect.x), y: Math.round(rect.y),
                       width: Math.round(rect.width), height: Math.round(rect.height)}
            };
        }'''
        target = await page.evaluate(describe, [x, y])
        if not target or target.get('tag') != 'iframe':
            return target
        # If the selected point falls inside a child frame, record the element
        # at that same point within the frame. This is observation only: the
        # worker does not search for, select, or solve a challenge control.
        for frame in getattr(page, 'frames', [])[1:]:
            try:
                element = await frame.frame_element()
                box = await element.bounding_box()
                if (box and box['x'] <= x < box['x'] + box['width']
                        and box['y'] <= y < box['y'] + box['height']):
                    target['frame'] = {
                        'url': str(frame.url)[:240],
                        'point': {'x': round(x - box['x'], 2),
                                  'y': round(y - box['y'], 2)},
                        'element': await frame.evaluate(
                            describe, [x - box['x'], y - box['y']]),
                    }
                    break
            except Exception:
                continue
        return target
    except Exception as exc:
        return {'inspection_error': type(exc).__name__}


async def _perform_user_click(page, x, y):
    """Replay only the human-selected point with a realistic pointer sequence."""
    mouse = page.mouse
    if all(hasattr(mouse, method) for method in ('move', 'down', 'up')):
        await mouse.move(x, y, steps=12)
        await asyncio.sleep(0.12)
        await mouse.down()
        await asyncio.sleep(0.08)
        await mouse.up()
        return
    # Compatibility fallback for older/mocked Playwright mouse objects.
    await mouse.click(x, y)


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
            screenshot_size = _png_size(screenshot)
            viewport = await _viewport(page)
            await emit(
                event='verification.screen_ready',
                message='Pantalla de verificación publicada con su geometría real.',
                viewport=viewport,
                screenshot=screenshot_size,
            )
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
                        # Forward only the coordinates submitted by the user,
                        # converting the published PNG space to CSS viewport
                        # coordinates instead of assuming both are identical.
                        await page.bring_to_front()
                        viewport = await _viewport(page)
                        try:
                            click_x, click_y = _map_click(
                                action[1], action[2], screenshot_size, viewport)
                        except ValueError as exc:
                            await emit(
                                event='verification.click_rejected', level='warning',
                                message='El clic no corresponde a la captura publicada; se conserva la sesión.',
                                received={'x': action[1], 'y': action[2]},
                                viewport=viewport, screenshot=screenshot_size,
                            )
                            raise ScrapingInterrupted(
                                'portal.paused: coordenadas de verificación inválidas; pendientes conservados') from exc
                        target_before = await _hit_target(page, click_x, click_y)
                        await _perform_user_click(page, click_x, click_y)
                        await asyncio.to_thread(exchange, 'executed', id=challenge_id)
                        await emit(event='verification.click_executed',
                                   message='El navegador ejecutó tu clic. Esto no confirma aún el acceso de Adondevivir.',
                                   received={'x': action[1], 'y': action[2]},
                                   used={'x': click_x, 'y': click_y},
                                   viewport=viewport, screenshot=screenshot_size,
                                   target_before=target_before)
                        # Give Turnstile time to process the interaction and
                        # require actual portal content before declaring success.
                        observe_until = min(deadline, time.monotonic() + POST_CLICK_WAIT_SECONDS)
                        while time.monotonic() < observe_until:
                            await asyncio.sleep(1)
                            await asyncio.to_thread(exchange, 'poll', id=challenge_id)
                            if await content_ready(page):
                                await emit(
                                    event='verification.completed',
                                    message='Adondevivir confirmó acceso después del clic; continúa la extracción.',
                                    received={'x': action[1], 'y': action[2]},
                                    used={'x': click_x, 'y': click_y},
                                )
                                return True
                            if not allowed_page(page):
                                raise ScrapingInterrupted(
                                    'portal.paused: dominio de verificación inesperado; pendientes conservados')
                        await emit(
                            event='verification.click_not_accepted', level='warning',
                            message='Adondevivir no confirmó el clic; se publicará una pantalla nueva antes de permitir otro intento.',
                            received={'x': action[1], 'y': action[2]},
                            used={'x': click_x, 'y': click_y},
                            viewport=await _viewport(page), screenshot=screenshot_size,
                            target_after=await _hit_target(page, click_x, click_y),
                        )
                    else:
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
