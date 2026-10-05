import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout

from scrapi.browser_verification import parse_action, content_ready, resolve
from scrapi.contracts import ScrapingInterrupted


class BrowserVerificationTests(unittest.IsolatedAsyncioTestCase):
    def page(self):
        return SimpleNamespace(url='https://www.adondevivir.com/inmuebles-en-venta-en-arequipa.html',
            title=AsyncMock(return_value='Just a moment...'),
            locator=Mock(return_value=SimpleNamespace(count=AsyncMock(return_value=1))),
            screenshot=AsyncMock(return_value=b'png'), set_viewport_size=AsyncMock(), bring_to_front=AsyncMock(),
            mouse=SimpleNamespace(click=AsyncMock()), _scraping_document_status=403)

    def test_coordinates_bounded_and_no_commands(self):
        self.assertEqual(parse_action('c:1439:999'), ('click', 1439, 999))
        self.assertEqual(parse_action('refresh'), ('refresh',))
        for raw in ('c:1440:100', 'c:10:1000', 'c:-1:4', 'c:nan:4', 'eval:x', 'https://other', '1', None):
            with self.assertRaises(ValueError): parse_action(raw)

    async def test_title_alone_never_confirms_access(self):
        page=self.page();page.title.return_value='Inmuebles en venta'
        self.assertFalse(await content_ready(page))
        page._scraping_document_status=200;page.locator.return_value.count.return_value=0
        self.assertFalse(await content_ready(page))
        page.locator.return_value.count.return_value=1
        self.assertTrue(await content_ready(page))

    async def test_only_user_click_is_forwarded_and_mailbox_closes(self):
        page=self.page();exchange=Mock(side_effect=['id', 'c:300:200', None, None])
        events = []
        page.bring_to_front.side_effect = lambda: events.append('focus')
        page.screenshot.side_effect = lambda **kwargs: events.append('screen') or b'png'
        page.mouse.click.side_effect = lambda *args: events.append('click')
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False,False,True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page,exchange,AsyncMock()))
        page.mouse.click.assert_awaited_once_with(300,200)
        self.assertEqual(events, ['focus', 'screen', 'focus', 'click'])
        self.assertEqual(exchange.call_args_list[-2].args, ('executed',))
        self.assertEqual(exchange.call_args_list[-2].kwargs, {'id': 'id'})
        self.assertEqual(exchange.call_args.args, ('close',))
        page.screenshot.assert_awaited_once()

    async def test_failed_click_is_never_acknowledged_as_executed(self):
        page = self.page()
        page.mouse.click.side_effect = RuntimeError('browser disconnected')
        exchange = Mock(side_effect=['id', 'c:300:200', None])
        emit = AsyncMock()
        with self.assertRaisesRegex(RuntimeError, 'disconnected'):
            await resolve(page, exchange, emit)
        self.assertNotIn('executed', [call.args[0] for call in exchange.call_args_list])
        self.assertNotIn('verification.click_executed', [call.kwargs.get('event') for call in emit.call_args_list])
        self.assertEqual(exchange.call_args.args, ('close',))

    async def test_refresh_does_not_click_or_reload(self):
        page=self.page();exchange=Mock(side_effect=['id','refresh',None])
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False,False,True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page,exchange,AsyncMock()))
        page.mouse.click.assert_not_awaited()

    async def test_screenshot_timeout_retries_same_page_then_publishes(self):
        page = self.page()
        page.screenshot.side_effect = [BrowserTimeout('taking page screenshot'), b'png']
        page.goto = AsyncMock()
        page.reload = AsyncMock()
        exchange = Mock(side_effect=['id', 'refresh', None])
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False, False, False, True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, exchange, AsyncMock()))
        self.assertEqual(page.screenshot.await_count, 2)
        self.assertEqual([call.args[0] for call in exchange.call_args_list], ['open', 'poll', 'close'])
        page.goto.assert_not_awaited()
        page.reload.assert_not_awaited()

    async def test_repeated_screenshot_timeouts_pause_instead_of_navigation_retry(self):
        page = self.page()
        page.screenshot.side_effect = BrowserTimeout('fonts loaded; screenshot timed out')
        exchange = Mock()
        with patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            with self.assertRaisesRegex(ScrapingInterrupted, '3 intentos.*pendientes conservados'):
                await resolve(page, exchange, AsyncMock())
        self.assertEqual(page.screenshot.await_count, 3)
        exchange.assert_called_once_with('close')
        page.mouse.click.assert_not_awaited()

    async def test_disconnected_browser_pauses_without_restarting_challenge(self):
        page = self.page()
        page.screenshot.side_effect = BrowserError('Target closed')
        exchange = Mock()
        with self.assertRaisesRegex(ScrapingInterrupted, 'falló el navegador'):
            await resolve(page, exchange, AsyncMock())
        page.screenshot.assert_awaited_once()
        exchange.assert_called_once_with('close')

    async def test_listing_does_not_navigate_again_after_capture_failure(self):
        from scrapi.paged_engine import navigate
        page = self.page()
        page.goto = AsyncMock(return_value=SimpleNamespace(status=403))
        page.screenshot.side_effect = BrowserTimeout('screenshot timed out')
        emit = AsyncMock()
        async def verify(target, **kwargs):
            return await resolve(target, Mock(), emit)
        source = SimpleNamespace(esperar_cloudflare=verify)
        with patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()), \
             patch('scrapi.paged_engine.wait_for_retry', AsyncMock()) as retry:
            with self.assertRaises(ScrapingInterrupted):
                await navigate(page, source, 'adondevivir', page.url, emit)
        page.goto.assert_awaited_once()
        retry.assert_not_awaited()

    async def test_cancel_from_worker_closes_mailbox(self):
        page=self.page();exchange=Mock(side_effect=['id',ScrapingInterrupted('stopped'),None])
        with self.assertRaisesRegex(ScrapingInterrupted,'stopped'):
            await resolve(page,exchange,AsyncMock())
        self.assertEqual(exchange.call_args.args, ('close',))
        page.mouse.click.assert_not_awaited()

    async def test_no_actions_after_navigation_away(self):
        page=self.page();page.url='https://other.example/'
        with self.assertRaisesRegex(ScrapingInterrupted,'dominio'):
            await resolve(page,Mock(),AsyncMock())
        page.mouse.click.assert_not_awaited();page.screenshot.assert_not_awaited()

    async def test_expired_challenge_preserves_pending_and_closes(self):
        page=self.page();exchange=Mock()
        with self.assertRaisesRegex(ScrapingInterrupted,'pendientes conservados'):
            await resolve(page,exchange,AsyncMock(),timeout=0)
        exchange.assert_called_once_with('close')
        page.mouse.click.assert_not_awaited()

    async def test_adondevivir_uses_human_callback_without_reloading(self):
        from scrapi import adondevivir_scraper as source
        page=self.page();page._manual_verification=AsyncMock(return_value=True)
        page.reload=AsyncMock()
        with patch.object(source,'_esperar_carga_real',AsyncMock(return_value=(False,''))):
            self.assertTrue(await source.esperar_cloudflare(page))
        page._manual_verification.assert_awaited_once_with(page)
        page.reload.assert_not_awaited()


if __name__ == '__main__': unittest.main()
