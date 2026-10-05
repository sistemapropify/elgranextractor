import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from scrapi.contracts import ScrapingInterrupted
from scrapi.native_verification import resolve_native


class NativeVerificationTests(unittest.IsolatedAsyncioTestCase):
    def page(self):
        return SimpleNamespace(url='https://www.adondevivir.com/inmuebles-en-venta-en-arequipa.html',
                               bring_to_front=AsyncMock(), mouse=Mock(), screenshot=Mock(), goto=Mock())

    async def test_waits_for_human_without_mouse_screenshot_or_reload(self):
        page = self.page()
        emit = AsyncMock()
        with patch('scrapi.native_verification.content_ready', AsyncMock(side_effect=[False, True])), \
             patch('scrapi.native_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve_native(page, emit))
        page.mouse.click.assert_not_called()
        page.screenshot.assert_not_called()
        page.goto.assert_not_called()
        self.assertEqual(emit.call_args.kwargs['event'], 'verification.completed')

    async def test_deadline_and_domain_do_not_claim_success(self):
        page = self.page()
        emit = AsyncMock()
        with self.assertRaises(ScrapingInterrupted):
            await resolve_native(page, emit, timeout=0)
        page.url = 'https://other.test/'
        with self.assertRaises(ScrapingInterrupted):
            await resolve_native(page, emit)

    def test_native_mode_rejects_remote_or_other_portals_before_launch(self):
        from scrapi.paged_engine import run_paged
        for portal, manual in [('urbania', None), ('adondevivir', Mock())]:
            with self.assertRaises(ValueError):
                run_paged(portal, source_url='https://www.adondevivir.com/',
                          native_verification=True, manual_verification=manual)
