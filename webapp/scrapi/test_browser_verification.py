import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from scrapi.browser_verification import parse_action, content_ready, resolve
from scrapi.contracts import ScrapingInterrupted


class BrowserVerificationTests(unittest.IsolatedAsyncioTestCase):
    def page(self):
        return SimpleNamespace(url='https://www.adondevivir.com/inmuebles-en-venta-en-arequipa.html',
            title=AsyncMock(return_value='Just a moment...'),
            locator=Mock(return_value=SimpleNamespace(count=AsyncMock(return_value=1))),
            screenshot=AsyncMock(return_value=b'png'), set_viewport_size=AsyncMock(),
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
        page=self.page();exchange=Mock(side_effect=['id', 'c:300:200', None])
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False,False,True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page,exchange,AsyncMock()))
        page.mouse.click.assert_awaited_once_with(300,200)
        self.assertEqual(exchange.call_args.args, ('close',))
        page.screenshot.assert_awaited_once()

    async def test_refresh_does_not_click_or_reload(self):
        page=self.page();exchange=Mock(side_effect=['id','refresh',None])
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False,False,True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page,exchange,AsyncMock()))
        page.mouse.click.assert_not_awaited()

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
