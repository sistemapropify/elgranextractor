import asyncio
import unittest
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout

from scrapi.browser_verification import _map_click, _png_size, parse_action, content_ready, resolve
from scrapi.contracts import ScrapingInterrupted


class BrowserVerificationTests(unittest.IsolatedAsyncioTestCase):
    def page(self):
        return SimpleNamespace(url='https://www.adondevivir.com/inmuebles-en-venta-en-arequipa.html',
            title=AsyncMock(return_value='Just a moment...'),
            locator=Mock(return_value=SimpleNamespace(count=AsyncMock(return_value=1))),
            screenshot=AsyncMock(return_value=b'png'), set_viewport_size=AsyncMock(), bring_to_front=AsyncMock(),
            mouse=SimpleNamespace(click=AsyncMock()), _scraping_document_status=403)

    def test_coordinates_bounded_and_no_commands(self):
        self.assertEqual(parse_action('c:2879:1999'), ('click', 2879, 1999))
        self.assertEqual(parse_action('refresh'), ('refresh',))
        for raw in ('c:8192:100', 'c:10:8192', 'c:-1:4', 'c:nan:4', 'eval:x', 'https://other', '1', None):
            with self.assertRaises(ValueError): parse_action(raw)

    def test_png_coordinates_are_mapped_to_css_viewport(self):
        png = b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 2880, 2000)
        size = _png_size(png)
        self.assertEqual(size, {'width': 2880, 'height': 2000})
        self.assertEqual(_map_click(600, 400, size, {'width': 1440, 'height': 1000}), (300, 200))
        with self.assertRaisesRegex(ValueError, 'fuera'):
            _map_click(2880, 400, size, {'width': 1440, 'height': 1000})

    async def test_title_alone_never_confirms_access(self):
        page=self.page();page.title.return_value='Inmuebles en venta'
        self.assertFalse(await content_ready(page))
        page._scraping_document_status=200;page.locator.return_value.count.return_value=0
        self.assertFalse(await content_ready(page))
        page.locator.return_value.count.return_value=1
        self.assertTrue(await content_ready(page))

    async def test_only_user_click_is_forwarded_and_mailbox_closes(self):
        page=self.page();exchange=Mock(side_effect=['id', 'c:300:200', None, None, None])
        events = []
        page.bring_to_front.side_effect = lambda: events.append('focus')
        page.screenshot.side_effect = lambda **kwargs: events.append('screen') or b'png'
        page.mouse.click.side_effect = lambda *args: events.append('click')
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False,False,True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page,exchange,AsyncMock()))
        page.mouse.click.assert_awaited_once_with(300,200)
        self.assertEqual(events, ['focus', 'screen', 'focus', 'click'])
        executed = next(call for call in exchange.call_args_list if call.args == ('executed',))
        self.assertEqual(executed.kwargs, {'id': 'id'})
        self.assertEqual(exchange.call_args.args, ('close',))
        page.screenshot.assert_awaited_once()

    async def test_click_diagnostics_record_real_geometry_and_hit_target(self):
        page = self.page()
        page.screenshot.return_value = (
            b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 2880, 2000))
        page.evaluate = AsyncMock(side_effect=[
            {'width': 1440, 'height': 1000, 'devicePixelRatio': 2, 'scrollX': 0, 'scrollY': 0},
            {'width': 1440, 'height': 1000, 'devicePixelRatio': 2, 'scrollX': 0, 'scrollY': 0},
            {'tag': 'iframe', 'id': '', 'className': '', 'title': 'Widget containing a Cloudflare security challenge',
             'src': 'https://challenges.cloudflare.com/', 'rect': {'x': 250, 'y': 300, 'width': 300, 'height': 65}},
        ])
        exchange = Mock(side_effect=['id', 'c:600:400', None, None, None])
        emit = AsyncMock()
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False, False, True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, exchange, emit))
        page.mouse.click.assert_awaited_once_with(300, 200)
        executed = next(call for call in emit.call_args_list
                        if call.kwargs.get('event') == 'verification.click_executed')
        self.assertEqual(executed.kwargs['received'], {'x': 600, 'y': 400})
        self.assertEqual(executed.kwargs['used'], {'x': 300, 'y': 200})
        self.assertEqual(executed.kwargs['target_before']['tag'], 'iframe')

    async def test_diagnostic_evaluation_failure_never_blocks_the_click(self):
        page = self.page()
        page.evaluate = AsyncMock(side_effect=TimeoutError('cross-origin frame stalled'))
        exchange = Mock(side_effect=['id', 'c:300:200', None, None, None])
        emit = AsyncMock()
        with patch('scrapi.browser_verification.content_ready',
                   AsyncMock(side_effect=[False, False, True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, exchange, emit))
        page.mouse.click.assert_awaited_once_with(300, 200)
        executed = next(call for call in emit.call_args_list
                        if call.kwargs.get('event') == 'verification.click_executed')
        self.assertEqual(
            executed.kwargs['target_before'],
            {'inspection_error': 'TimeoutError'},
        )

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

    async def test_unaccepted_click_is_reported_and_never_marked_completed(self):
        page = self.page()
        page.mouse = SimpleNamespace(
            move=AsyncMock(), down=AsyncMock(), up=AsyncMock(), click=AsyncMock())
        exchange = Mock(side_effect=[
            'id', 'c:300:200', None,
            ScrapingInterrupted('stopped after refreshed screen'), None])
        emit = AsyncMock()
        with patch('scrapi.browser_verification.content_ready', AsyncMock(return_value=False)), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()), \
             patch('scrapi.browser_verification.POST_CLICK_WAIT_SECONDS', 0):
            with self.assertRaisesRegex(ScrapingInterrupted, 'stopped'):
                await resolve(page, exchange, emit)
        page.mouse.click.assert_awaited_once_with(300, 200)
        page.mouse.move.assert_not_awaited()
        page.mouse.down.assert_not_awaited()
        page.mouse.up.assert_not_awaited()
        events = [call.kwargs.get('event') for call in emit.call_args_list]
        self.assertIn('verification.click_executed', events)
        self.assertIn('verification.click_not_accepted', events)
        self.assertNotIn('verification.completed', events)

    async def test_post_click_feedback_is_published_while_acceptance_is_pending(self):
        page = self.page()
        polls = 0
        feedbacks = []
        def exchange(action, **payload):
            nonlocal polls
            if action == 'open': return 'id'
            if action == 'poll':
                polls += 1
                return 'c:300:200' if polls == 1 else None
            if action == 'feedback': feedbacks.append(payload)
        # Access remains blocked for the first post-click observation, then
        # becomes ready. The intermediate screen must reach the mailbox.
        with patch('scrapi.browser_verification.content_ready',
                   AsyncMock(side_effect=[False, False, False, True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, exchange, AsyncMock()))
        self.assertEqual(feedbacks, [{'id': 'id', 'screenshot': 'cG5n'}])
        self.assertEqual(page.screenshot.await_count, 2)
        page.mouse.click.assert_awaited_once_with(300, 200)

    async def test_humanized_pointer_never_uses_a_multistep_move(self):
        page = self.page()
        # This is the real mouse API shape, unlike the minimal click-only mock.
        # An extra move must not delay the human action or prevent button-down.
        page.mouse = SimpleNamespace(
            move=AsyncMock(side_effect=AssertionError('duplicate interpolation')),
            down=AsyncMock(), up=AsyncMock(), click=AsyncMock())
        exchange = Mock(side_effect=['id', 'c:300:200', None, None])
        with patch('scrapi.browser_verification.content_ready',
                   AsyncMock(side_effect=[False, False, True])):
            self.assertTrue(await resolve(page, exchange, AsyncMock()))
        page.mouse.click.assert_awaited_once_with(300, 200)
        page.mouse.move.assert_not_awaited()
        page.mouse.down.assert_not_awaited()
        page.mouse.up.assert_not_awaited()

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
        with patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False, False, True])), \
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

    async def stalled(self, *args, **kwargs):
        # A genuinely pending operation, not an exception supplied by a mock.
        await asyncio.Event().wait()

    async def test_pending_title_and_dom_reads_have_a_real_deadline(self):
        for field in ('title', 'count'):
            with self.subTest(field=field):
                page = self.page()
                page.title.return_value = 'Inmuebles en venta'
                target = page.title if field == 'title' else page.locator.return_value.count
                target.side_effect = self.stalled
                with patch('scrapi.browser_verification.CONTENT_TIMEOUT_SECONDS', .01):
                    self.assertFalse(await asyncio.wait_for(content_ready(page), .5))

    async def test_title_stall_after_consuming_action_does_not_block_click(self):
        page = self.page()
        calls = 0
        async def title():
            nonlocal calls
            calls += 1
            if calls == 2:
                await self.stalled()
            return 'Just a moment' if calls == 1 else 'Inmuebles en venta'
        page.title.side_effect = title
        page.mouse.click.side_effect = lambda *args: setattr(page, '_scraping_document_status', 200)
        exchange = Mock(side_effect=['id', 'c:300:200', None, None, None])
        emit = AsyncMock()
        with patch('scrapi.browser_verification.CONTENT_TIMEOUT_SECONDS', .01), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await asyncio.wait_for(resolve(page, exchange, emit), .5))
        page.mouse.click.assert_awaited_once_with(300, 200)
        self.assertIn('verification.content_check_timeout', [c.kwargs.get('event') for c in emit.call_args_list])
        self.assertEqual(exchange.call_args.args, ('close',))

    async def test_focus_resize_and_mouse_stalls_pause_with_the_exact_phase(self):
        for phase in ('focus', 'resize', 'mouse_click'):
            with self.subTest(phase=phase):
                page, emit = self.page(), AsyncMock()
                target = {'focus': page.bring_to_front, 'resize': page.set_viewport_size,
                          'mouse_click': page.mouse.click}[phase]
                target.side_effect = self.stalled
                def mail(action, **kwargs):
                    return {'open': 'id', 'poll': 'c:300:200'}.get(action)
                exchange = Mock(side_effect=mail)
                # Keep the deliberate browser stall bounded without racing
                # Windows thread-pool scheduling of the healthy mailbox.
                with patch('scrapi.browser_verification.BROWSER_TIMEOUT_SECONDS', .1):
                    with self.assertRaisesRegex(ScrapingInterrupted, phase):
                        await asyncio.wait_for(resolve(page, exchange, emit), 2)
                self.assertNotIn('executed', [call.args[0] for call in exchange.call_args_list])
                timeout_log = next(c for c in emit.call_args_list
                                   if c.kwargs.get('event') == 'verification.browser_timeout')
                self.assertEqual(timeout_log.kwargs['phase'], phase)
                self.assertEqual(exchange.call_args.args, ('close',))

    async def test_screenshot_stall_is_bounded_even_if_driver_ignores_timeout(self):
        page, emit, exchange = self.page(), AsyncMock(), Mock()
        page.screenshot.side_effect = self.stalled
        page.goto, page.reload = AsyncMock(), AsyncMock()
        with patch('scrapi.browser_verification.BROWSER_TIMEOUT_SECONDS', .02), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            with self.assertRaisesRegex(ScrapingInterrupted, '3 intentos'):
                await asyncio.wait_for(resolve(page, exchange, emit), .5)
        self.assertEqual(page.screenshot.await_count, 3)
        page.goto.assert_not_awaited()
        page.reload.assert_not_awaited()
        exchange.assert_called_once_with('close')

    async def test_wall_deadline_cancels_a_pending_browser_step(self):
        page, exchange, emit = self.page(), Mock(), AsyncMock()
        page.bring_to_front.side_effect = self.stalled
        # The total budget is smaller than the per-operation timeout.
        with self.assertRaisesRegex(ScrapingInterrupted, 'focus'):
            await asyncio.wait_for(resolve(page, exchange, emit, timeout=.02), .5)
        exchange.assert_called_once_with('close')

    async def test_pending_diagnostics_do_not_block_a_human_click(self):
        page, exchange = self.page(), Mock(side_effect=['id', 'c:300:200', None, None, None])
        page.evaluate = AsyncMock(side_effect=self.stalled)
        with patch('scrapi.browser_verification.DIAGNOSTIC_TIMEOUT_SECONDS', .01), \
             patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False, False, True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await asyncio.wait_for(resolve(page, exchange, AsyncMock()), .5))
        page.mouse.click.assert_awaited_once_with(300, 200)

    async def test_screen_refreshes_without_any_human_action_or_reload(self):
        page, emit = self.page(), AsyncMock()
        page.goto, page.reload = AsyncMock(), AsyncMock()
        def mail(action, **kwargs):
            if action == 'open': return 'first'
            if action == 'refresh':
                self.assertEqual(kwargs['id'], 'first')
                return 'second'
            if action == 'poll' and kwargs['id'] == 'second':
                raise ScrapingInterrupted('test finished after automatic refresh')
        exchange = Mock(side_effect=mail)
        with patch('scrapi.browser_verification.SCREEN_REFRESH_SECONDS', 0), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            with self.assertRaisesRegex(ScrapingInterrupted, 'test finished'):
                await resolve(page, exchange, emit)
        self.assertEqual(page.screenshot.await_count, 2)
        self.assertIn('verification.screen_refreshed', [c.kwargs.get('event') for c in emit.call_args_list])
        page.mouse.click.assert_not_awaited()
        page.goto.assert_not_awaited()
        page.reload.assert_not_awaited()

    async def test_answer_arriving_during_capture_keeps_original_geometry(self):
        page = self.page()
        page.screenshot.side_effect = [
            b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', w, h)
            for w, h in ((1440, 1000), (2880, 2000))]
        polls = iter([None, 'c:300:200', None])
        def mail(action, **kwargs):
            if action == 'open': return 'original'
            if action == 'poll':
                self.assertEqual(kwargs['id'], 'original')
                return next(polls)
            # Rotation refused because a human submitted while we captured.
            if action == 'refresh': return None
        exchange = Mock(side_effect=mail)
        with patch('scrapi.browser_verification.SCREEN_REFRESH_SECONDS', 0), \
             patch('scrapi.browser_verification.content_ready', AsyncMock(side_effect=[False, False, False, True])), \
             patch('scrapi.browser_verification.asyncio.sleep', AsyncMock()):
            self.assertTrue(await resolve(page, exchange, AsyncMock()))
        page.mouse.click.assert_awaited_once_with(300, 200)
        self.assertEqual(page.screenshot.await_count, 2)


if __name__ == '__main__': unittest.main()
