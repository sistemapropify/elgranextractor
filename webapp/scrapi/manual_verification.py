"""Forward a human's answer to the existing page. No automatic solver."""
import asyncio
import base64
import logging
import time
from urllib.parse import urlsplit
from .contracts import ScrapingInterrupted

logger = logging.getLogger(__name__)


class HumanAnswerNotAccepted(RuntimeError):
    """The portal did not enable its submit control; no answer was submitted."""


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
    await asyncio.wait_for(page.bring_to_front(), timeout=5)
    # Some challenges enable their button on keyboard events, which fill()
    # does not generate. Type only the bounded answer supplied by the human.
    await field.fill('', timeout=5000)
    await field.press_sequentially(answer, delay=40, timeout=5000)
    try:
        diagnostics = {'button_enabled': await button.is_enabled(timeout=2000),
                       'button_visible': await button.is_visible(),
                       'input_matches_human_response': await field.input_value(timeout=2000) == answer}
    except Exception as exc:
        diagnostics = {'inspection_error': type(exc).__name__}
    await emit(event='verification.input_ready',
        message='Respuesta colocada en el formulario; comprobando si Properati permite enviarla.',
        **diagnostics)
    try:
        # Blurring the field lets pages that enable the button on change/blur
        # finish their own validation before Playwright checks actionability.
        await field.press('Tab', timeout=3000)
    except Exception:
        pass

    try:
        # The page may validate input asynchronously after blur. Observe its
        # own enabled state; never remove disabled or force a click.
        for observation in range(11):
            if await _content_ready(page):
                return
            if await button.is_enabled(timeout=2000):
                break
            if observation < 10:
                await asyncio.sleep(0.5)
        else:
            raise HumanAnswerNotAccepted()
        await button.click(timeout=5000)
        return
    except HumanAnswerNotAccepted:
        raise
    except Exception as click_error:
        # Some challenge implementations submit on input/change and remove the
        # button while click() is waiting. That is already a successful submit.
        await asyncio.sleep(1)
        if await _content_ready(page):
            logger.info('Properati verification completed while the submit button changed')
            return
        logger.warning(
            'Properati verification button was not actionable (%s); trying native Enter',
            type(click_error).__name__,
        )
        await emit(
            event='verification.submit_fallback', level='warning',
            message='El clic del navegador no terminó; enviando tu misma respuesta con la tecla Enter.',
        )

    # A synthetic DOM click may return successfully without submitting a
    # disabled form. Use a native keyboard event for the human's answer.
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
    session_deadline = time.monotonic() + 900
    try:
        for attempt in range(3):
            # Every human attempt needs its own usable response window.
            # Still cap the whole verification session at fifteen minutes.
            deadline = min(session_deadline, time.monotonic() + 300)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise manual_timeout()
            screenshot = await page.locator('.custom-captcha').screenshot(timeout=10000)
            challenge_id = await asyncio.to_thread(exchange, 'open',
                screenshot=base64.b64encode(screenshot).decode('ascii'), seconds=remaining)
            await emit(event='verification.required', level='warning',
                message=f'Properati requiere tu respuesta en el dashboard. Esta imagen vence en {int(remaining)} segundos.')
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
            try:
                await _submit_human_answer(page, answer, emit)
            except HumanAnswerNotAccepted:
                await emit(event='verification.answer_not_accepted', level='warning',
                    message='Properati mantiene deshabilitado el botón de envío. La respuesta no se envió. Revisa la nueva imagen antes de responder de nuevo.')
                continue
            await asyncio.to_thread(exchange, 'executed', id=challenge_id)
            await emit(event='verification.submitted',
                message='El navegador procesó tu respuesta; esperando que Properati confirme el acceso.')
            # Wait for actual listing/detail content, not just a changed title.
            for observation in range(15):
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
                if observation in (0, 4):
                    # Let the human see the real post-submit portal screen.
                    # Neither the answer nor the screenshot enters the logs.
                    try:
                        screenshot = await page.locator('.custom-captcha').screenshot(timeout=5000)
                    except Exception as exc:
                        await emit(event='verification.feedback_unavailable', level='debug',
                            error_type=type(exc).__name__,
                            message='Properati está cambiando la pantalla; se comprobará otra vez.')
                    else:
                        await asyncio.to_thread(exchange, 'feedback', id=challenge_id,
                            screenshot=base64.b64encode(screenshot).decode('ascii'))
            if not await page.locator('#math-answer').count():
                raise manual_timeout()
            await emit(event='verification.retry', level='warning',
                message='La verificación no fue aceptada; revisa la nueva captura antes de responder.')
        raise manual_timeout()
    finally:
        await asyncio.to_thread(exchange, 'close')
