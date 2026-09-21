import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from scrapi.manual_verification import resolve
from scrapi.contracts import ScrapingInterrupted


class ManualVerificationTests(unittest.IsolatedAsyncioTestCase):
    def page(self):
        self.solved = False
        async def press(key, **kwargs):
            if key == 'Enter':
                self.solved = True
        self.field = SimpleNamespace(
            count=AsyncMock(side_effect=lambda: int(not self.solved)),
            fill=AsyncMock(), press=AsyncMock(side_effect=press),
        )
        async def click(**kwargs):
            self.solved = True
        async def dom_click(script):
            self.solved = True
        self.button = SimpleNamespace(
            count=AsyncMock(return_value=1), click=AsyncMock(side_effect=click),
            evaluate=AsyncMock(side_effect=dom_click),
        )
        self.image = SimpleNamespace(screenshot=AsyncMock(return_value=b'png'))
        selectors = {'#math-answer': self.field, '#verify-btn': self.button,
                     '.custom-captcha': self.image,
                     'article.snippet, #location-map': SimpleNamespace(count=AsyncMock(return_value=1))}
        return SimpleNamespace(url='https://www.properati.com.pe/detalle/example', locator=selectors.__getitem__)

    async def test_only_human_answer_is_sent_in_same_page(self):
        page = self.page()
        def exchange(action, **kwargs):
            return 'id' if action == 'open' else ('123' if action == 'poll' else None)
        mailbox = Mock(side_effect=exchange)
        emit = AsyncMock()
        with patch('scrapi.manual_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, mailbox, emit))
        self.field.fill.assert_awaited_once_with('123', timeout=5000)
        self.button.click.assert_awaited_once()
        self.assertEqual(mailbox.call_args.args, ('close',))
        self.assertIn('verification.resolved', [c.kwargs['event'] for c in emit.call_args_list])
        self.assertNotIn('123', str(emit.call_args_list))
        self.assertIsNone(page._scraping_initial_html)

    async def test_stopped_job_cannot_submit_to_browser(self):
        page = self.page()
        def exchange(action, **kwargs):
            if action == 'poll':
                raise ScrapingInterrupted('stopped')
            return 'id'
        mailbox = Mock(side_effect=exchange)
        with self.assertRaises(ScrapingInterrupted):
            await resolve(page, mailbox, AsyncMock())
        self.field.fill.assert_not_awaited()
        self.assertEqual(mailbox.call_args.args, ('close',))

    async def test_other_origin_never_receives_input(self):
        page = self.page()
        page.url = 'https://other.example/'
        mailbox = Mock()
        self.assertFalse(await resolve(page, mailbox, AsyncMock()))
        mailbox.assert_not_called()

    async def test_expiry_does_not_click_or_loop_retries(self):
        page = self.page()
        mailbox = Mock()
        with patch('scrapi.manual_verification.time.monotonic', side_effect=[0, 301]):
            with self.assertRaisesRegex(ScrapingInterrupted, 'portal.paused:'):
                await resolve(page, mailbox, AsyncMock())
        self.button.click.assert_not_awaited()
        mailbox.assert_called_once_with('close')

    async def test_changed_portal_button_uses_dom_click_fallback(self):
        page = self.page()
        self.button.click.side_effect = TimeoutError()
        mailbox = Mock(side_effect=lambda action, **kwargs: 'id' if action == 'open' else '123')
        with patch('scrapi.manual_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, mailbox, AsyncMock()))
        self.button.evaluate.assert_awaited_once()
        self.assertEqual(mailbox.call_args.args, ('close',))

    async def test_disappearing_button_after_fill_is_accepted_when_content_loaded(self):
        page = self.page()
        async def fill_and_resolve(answer, **kwargs):
            self.solved = True
        self.field.fill.side_effect = fill_and_resolve
        self.button.click.side_effect = TimeoutError()
        mailbox = Mock(side_effect=lambda action, **kwargs: 'id' if action == 'open' else '123')
        with patch('scrapi.manual_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, mailbox, AsyncMock()))
        self.button.evaluate.assert_not_awaited()

    async def test_all_submit_methods_unavailable_stops_with_pending_intact(self):
        page = self.page()
        self.button.click.side_effect = TimeoutError()
        self.button.count.side_effect = [1, 0]
        self.field.press.side_effect = TimeoutError()
        mailbox = Mock(side_effect=lambda action, **kwargs: 'id' if action == 'open' else '123')
        with patch('scrapi.manual_verification.asyncio.sleep', AsyncMock()):
            with self.assertRaisesRegex(ScrapingInterrupted, 'no permitió enviar'):
                await resolve(page, mailbox, AsyncMock())
        self.assertEqual(mailbox.call_args.args, ('close',))
