"""Forward a human's answer to the existing page. No automatic solver."""
import asyncio
import base64
import time
from urllib.parse import urlsplit
from .contracts import ScrapingInterrupted


def manual_timeout():
    return ScrapingInterrupted('portal.paused: verificación manual no completada; pendientes conservados')


async def resolve(page, exchange, emit):
    if urlsplit(page.url).hostname != 'www.properati.com.pe':
        return False
    if not await page.locator('#math-answer').count() or not await page.locator('#verify-btn').count():
        return False
    deadline = time.monotonic() + 300
    try:
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise manual_timeout()
            screenshot = await page.locator('.custom-captcha').screenshot(timeout=10000)
            challenge_id = await asyncio.to_thread(exchange, 'open',
                screenshot=base64.b64encode(screenshot).decode('ascii'), seconds=remaining)
            await emit(event='verification.required', level='warning',
                message='Properati requiere tu respuesta: completa la verificación en el dashboard (máximo 5 minutos).')
            answer = None
            while time.monotonic() < deadline:
                # Also checks that pause/stop/worker replacement hasn't invalidated this browser.
                answer = await asyncio.to_thread(exchange, 'poll', id=challenge_id)
                if answer is not None:
                    break
                await asyncio.sleep(2)
            if answer is None:
                raise manual_timeout()
            if urlsplit(page.url).hostname != 'www.properati.com.pe':
                raise manual_timeout()
            await page.locator('#math-answer').fill(answer, timeout=5000)
            try:
                await page.locator('#verify-btn').click(timeout=10000)
            except Exception as exc:
                raise ScrapingInterrupted('portal.paused: el botón de verificación no está disponible; pendientes conservados') from exc
            # Wait for actual listing/detail content, not just a changed title.
            for _ in range(10):
                await asyncio.sleep(2)
                await asyncio.to_thread(exchange, 'poll', id=challenge_id)
                if time.monotonic() >= deadline:
                    raise manual_timeout()
                if urlsplit(page.url).hostname != 'www.properati.com.pe':
                    raise manual_timeout()
                if not await page.locator('#math-answer').count():
                    if await page.locator('article.snippet, #location-map').count():
                        page._scraping_initial_html = None
                        page._scraping_initial_url = None
                        await emit(event='verification.resolved',
                            message='Properati aceptó la verificación; continúa la extracción.')
                        return True
            if not await page.locator('#math-answer').count():
                raise manual_timeout()
            await emit(event='verification.retry', level='warning',
                message='La verificación no fue aceptada; revisa la nueva captura antes de responder.')
        raise manual_timeout()
    finally:
        await asyncio.to_thread(exchange, 'close')
