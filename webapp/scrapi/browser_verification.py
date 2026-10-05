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
DIAGNOSTIC_TIMEOUT_SECONDS = 0.75
CONTENT_TIMEOUT_SECONDS = 2
BROWSER_TIMEOUT_SECONDS = 10
SCREEN_REFRESH_SECONDS = 8
CLEANUP_TIMEOUT_SECONDS = 5


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
        result = await asyncio.wait_for(
            page.evaluate('''() => ({
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio,
                scrollX: window.scrollX,
                scrollY: window.scrollY
            })'''),
            timeout=DIAGNOSTIC_TIMEOUT_SECONDS,
        )
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
        target = await asyncio.wait_for(
            page.evaluate(describe, [x, y]),
            timeout=DIAGNOSTIC_TIMEOUT_SECONDS,
        )
        if target and target.get('tag') == 'iframe':
            # Frame URLs are synchronous Playwright metadata. Never evaluate
            # the cross-origin challenge frame before clicking: in production
            # that inspection can wait indefinitely and consume the action
            # without ever reaching page.mouse.
            target['frame_urls'] = [str(frame.url)[:240]
                                    for frame in getattr(page, 'frames', [])[1:6]]
        return target
    except Exception as exc:
        return {'inspection_error': type(exc).__name__}


async def _perform_user_click(page, x, y):
    """Replay exactly one click at the point selected by the human.

    Camoufox already interpolates pointer movement with humanize enabled.
    Twelve Playwright steps invoke that interpolation twelve times, consuming
    the operation's deadline before button-down. A single native click moves,
    presses and releases without duplicating interpolation or leaving our own
    separately scheduled button-down pending on cancellation.
    """
    await page.mouse.click(x, y)


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


async def content_ready(page, on_timeout=None):
    try:
        # title() and count() have no useful default timeout. In particular, a
        # stalled title read after consuming a mailbox action could prevent
        # the worker from ever reaching the click or the next screenshot.
        return await asyncio.wait_for(_content_ready(page), CONTENT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        if on_timeout:
            await on_timeout()
        return False
    except Exception:
        # Navigation can destroy the document between title and DOM reads.
        return False


async def resolve(page, exchange, emit, timeout=300):
    if not allowed_page(page):
        raise ScrapingInterrupted('portal.paused: Adondevivir cambió de dominio; pendientes conservados')
    budget = max(0, min(timeout, 300))
    deadline = time.monotonic() + budget
    phase = 'initializing'

    async def step(name, operation, announce=True):
        nonlocal phase
        phase = name
        if announce:
            await emit(event='verification.browser_step', level='debug', phase=name,
                       message=f'Verificación: paso del navegador {name}.')
        return await asyncio.wait_for(operation(), BROWSER_TIMEOUT_SECONDS)

    try:
        # The wall-clock deadline must cancel pending browser/DB/log awaits,
        # not merely be checked when the polling loop gets control again.
        return await asyncio.wait_for(
            _resolve(page, exchange, emit, deadline, step), budget)
    except asyncio.TimeoutError as exc:
        try:
            await asyncio.wait_for(emit(
                event='verification.browser_timeout', level='warning', phase=phase,
                message=f'La verificación agotó el tiempo en el paso {phase}. '
                        'Se pausa sin recargar el portal; pendientes conservados.'),
                CLEANUP_TIMEOUT_SECONDS)
        except Exception:
            pass  # Do not let a stalled log sink mask the original failure.
        raise ScrapingInterrupted(
            f'portal.paused: tiempo agotado en verificación ({phase}); pendientes conservados') from exc
    except BrowserError as exc:
        raise ScrapingInterrupted(
            f'portal.paused: falló el navegador durante la verificación ({phase}); '
            'no se recargará el portal; pendientes conservados') from exc
    finally:
        # Cleanup also has a bound. The mailbox expiry remains the fallback if
        # its database is unavailable, and rejects late actions on its own.
        try:
            await asyncio.wait_for(asyncio.to_thread(exchange, 'close'), CLEANUP_TIMEOUT_SECONDS)
        except Exception:
            pass


async def _resolve(page, exchange, emit, deadline, step):
    await emit(event='verification.required', level='warning',
               message='Adondevivir requiere verificación: abre la pantalla en el dashboard y responde allí. '
                       'Se mantiene el navegador de producción durante 5 minutos.')

    async def capture():
        for attempt in range(1, 4):
            try:
                return await step('screenshot', lambda: page.screenshot(
                    type='png', full_page=False, scale='css',
                    timeout=max(1, min(10000, int((deadline - time.monotonic()) * 1000)))))
            except (BrowserTimeout, asyncio.TimeoutError) as exc:
                await emit(event='verification.screenshot_failed', level='warning', phase='screenshot',
                           message=f'La captura de verificación agotó su tiempo ({attempt}/3). '
                                   'Se conserva la misma pestaña, sin recargar el portal.')
                if attempt == 3:
                    raise ScrapingInterrupted(
                        'portal.paused: el navegador no pudo capturar la verificación tras 3 intentos; '
                        'no se recargará el portal; pendientes conservados') from exc
                await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))

    content_timeout_reported = False

    async def report_content_timeout():
        nonlocal content_timeout_reported
        if not content_timeout_reported:
            content_timeout_reported = True
            await emit(event='verification.content_check_timeout', level='warning', phase='content_check',
                       message='El navegador no respondió al consultar el título o contenido. '
                               'La consulta se canceló; se intentará actualizar la captura sin recargar el portal.')

    async def ready():
        return await step('content_check', lambda: content_ready(page, on_timeout=report_content_timeout), announce=False)

    async def mail(action, **payload):
        return await step('mailbox_' + action, lambda: asyncio.to_thread(exchange, action, **payload), announce=False)

    async def screen_event(screenshot, viewport, *, refreshed=False):
        await emit(event='verification.screen_refreshed' if refreshed else 'verification.screen_ready',
                   message='Pantalla actualizada automáticamente, sin recargar el portal.' if refreshed
                           else 'Pantalla de verificación publicada con su geometría real.',
                   viewport=viewport, screenshot=_png_size(screenshot))

    # Listing and detail share a context but are separate tabs. The human
    # must interact with the tab represented by this screenshot.
    await step('focus', page.bring_to_front)
    await step('resize', lambda: page.set_viewport_size({'width': WIDTH, 'height': HEIGHT}))
    while time.monotonic() < deadline:
        if await ready():
            await emit(event='verification.completed', message='Adondevivir confirmó acceso; continúa la extracción.')
            return True
        if not allowed_page(page):
            break
        screenshot = await capture()
        screenshot_size = _png_size(screenshot)
        viewport = await step('viewport', lambda: _viewport(page), announce=False)
        challenge_id = await mail('open',
            screenshot=base64.b64encode(screenshot).decode('ascii'),
            seconds=max(1, int(deadline-time.monotonic())))
        await screen_event(screenshot, viewport)
        refresh_at = time.monotonic() + SCREEN_REFRESH_SECONDS
        while time.monotonic() < deadline:
            answer = await mail('poll', id=challenge_id)
            if await ready():
                await emit(event='verification.completed', message='Adondevivir confirmó acceso; continúa la extracción.')
                return True
            if not allowed_page(page):
                raise ScrapingInterrupted('portal.paused: dominio de verificación inesperado; pendientes conservados')
            if answer is not None:
                action = parse_action(answer)
                await emit(event='verification.action_received', action=action[0],
                           message='El worker procesa tu clic.' if action[0] == 'click'
                                   else 'El worker prepara una nueva captura sin recargar el portal.')
                if action[0] == 'click':
                    await step('focus', page.bring_to_front)
                    viewport = await step('viewport', lambda: _viewport(page), announce=False)
                    try:
                        click_x, click_y = _map_click(action[1], action[2], screenshot_size, viewport)
                    except ValueError as exc:
                        await emit(event='verification.click_rejected', level='warning',
                                   message='El clic no corresponde a la captura publicada; se conserva la sesión.',
                                   received={'x': action[1], 'y': action[2]},
                                   viewport=viewport, screenshot=screenshot_size)
                        raise ScrapingInterrupted(
                            'portal.paused: coordenadas de verificación inválidas; pendientes conservados') from exc
                    target_before = await step('hit_target', lambda: _hit_target(page, click_x, click_y), announce=False)
                    await step('mouse_click', lambda: _perform_user_click(page, click_x, click_y))
                    await mail('executed', id=challenge_id)
                    await emit(event='verification.click_executed',
                               message='El navegador ejecutó tu clic. Esto no confirma aún el acceso de Adondevivir.',
                               received={'x': action[1], 'y': action[2]}, used={'x': click_x, 'y': click_y},
                               viewport=viewport, screenshot=screenshot_size, target_before=target_before)
                    observe_until = min(deadline, time.monotonic() + POST_CLICK_WAIT_SECONDS)
                    feedback_at = time.monotonic()
                    first_observation = True
                    while time.monotonic() < observe_until:
                        await asyncio.sleep(.25 if first_observation else 1)
                        first_observation = False
                        await mail('poll', id=challenge_id)
                        if await ready():
                            await emit(event='verification.completed',
                                       message='Adondevivir confirmó acceso después del clic; continúa la extracción.',
                                       received={'x': action[1], 'y': action[2]}, used={'x': click_x, 'y': click_y})
                            return True
                        if not allowed_page(page):
                            raise ScrapingInterrupted(
                                'portal.paused: dominio de verificación inesperado; pendientes conservados')
                        if time.monotonic() >= feedback_at:
                            try:
                                feedback = await asyncio.wait_for(page.screenshot(
                                    type='png', full_page=False, scale='css', timeout=1500), 2)
                            except (BrowserError, asyncio.TimeoutError):
                                # Feedback is best-effort, never replay the click
                                # or abort it just because one frame was slow.
                                feedback = None
                            if feedback is not None and allowed_page(page):
                                await mail('feedback', id=challenge_id,
                                           screenshot=base64.b64encode(feedback).decode('ascii'))
                            feedback_at = time.monotonic() + 2
                    await emit(event='verification.click_not_accepted', level='warning',
                               message='Adondevivir no confirmó el clic; se publicará una pantalla nueva antes de permitir otro intento.',
                               received={'x': action[1], 'y': action[2]}, used={'x': click_x, 'y': click_y},
                               viewport=await _viewport(page), screenshot=screenshot_size,
                               target_after=await _hit_target(page, click_x, click_y))
                else:
                    await asyncio.sleep(1)
                break
            if time.monotonic() >= refresh_at:
                next_screen = await capture()
                if not allowed_page(page):
                    raise ScrapingInterrupted('portal.paused: dominio de verificación inesperado; pendientes conservados')
                # Atomic rotation: an answer submitted during capture wins.
                # Never discard it, and never replay an old ID on a new image.
                next_id = await mail('refresh', id=challenge_id,
                                     screenshot=base64.b64encode(next_screen).decode('ascii'))
                if next_id:
                    challenge_id = next_id
                    screenshot_size = _png_size(next_screen)
                    await screen_event(next_screen, await _viewport(page), refreshed=True)
                refresh_at = time.monotonic() + SCREEN_REFRESH_SECONDS
            await asyncio.sleep(1)
    raise ScrapingInterrupted('portal.paused: Adondevivir no confirmó la verificación; pendientes conservados')
