"""Forward a human's answer to the existing page. No automatic solver."""
import asyncio
import base64
import logging
import time
from urllib.parse import urlsplit
from .contracts import ScrapingInterrupted

logger = logging.getLogger(__name__)


def manual_timeout():
    return ScrapingInterrupted('portal.paused: verificación manual no completada; pendientes conservados')


async def _content_ready(page):
    """The challenge disappeared and the requested Properati content is present."""
    if await page.locator('#math-answer').count():
        return False
    return bool(await page.locator('article.snippet, #location-map').count())


async def _submit_human_answer(page, answer, emit):
    """Submit one human answer despite transient button/actionability changes."""
    field = page.locator('#math-answer')
    button = page.locator('#verify-btn')
    await field.fill(answer, timeout=5000)
    try:
        # Blurring the field lets pages that enable the button on change/blur
        # finish their own validation before Playwright checks actionability.
        await field.press('Tab', timeout=3000)
    except Exception:
        pass

    try:
        await button.click(timeout=5000)
        return
    except Exception as click_error:
        # Some challenge implementations submit on input/change and remove the
        # button while click() is waiting. That is already a successful submit.
        await asyncio.sleep(1)
        if await _content_ready(page):
            logger.info('Properati verification completed while the submit button changed')
            return
        logger.warning(
            'Properati verification button was not actionable (%s); trying form submission fallback',
            type(click_error).__name__,
        )
        await emit(
            event='verification.submit_fallback', level='warning',
            message='Properati cambió el botón; reenviando tu respuesta en la misma verificación.',
        )

    # A DOM click avoids false negatives caused only by an overlay/animation,
    # while still sending exactly the answer supplied by the human.
    if await button.count():
        try:
            await button.evaluate('(element) => element.click()')
            return
        except Exception:
            pass
    try:
        await field.press('Enter', timeout=5000)
    except Exception as enter_error:
        await asyncio.sleep(1)
        if await _content_ready(page):
            return
        logger.warning(
            'Properati verification fallback failed (%s)', type(enter_error).__name__,
        )
        raise ScrapingInterrupted(
            'portal.paused: Properati no permitió enviar la respuesta; pendientes conservados'
        ) from enter_error


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
            await _submit_human_answer(page, answer, emit)
            # Wait for actual listing/detail content, not just a changed title.
            for _ in range(15):
                await asyncio.sleep(2)
                await asyncio.to_thread(exchange, 'poll', id=challenge_id)
                if time.monotonic() >= deadline:
                    raise manual_timeout()
                if urlsplit(page.url).hostname != 'www.properati.com.pe':
                    raise manual_timeout()
                if await _content_ready(page):
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
