from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import ExitStack
from scrapi import facebook_marketplace_scraper as fb
from scrapi.contracts import ScrapingInterrupted


class FakePage:
    def __init__(self, blocks):
        self.blocks = blocks
        self.round = 0
        self.url = fb.DEFAULT_SEARCH_URL
        self.mouse = SimpleNamespace(move=AsyncMock(), wheel=AsyncMock())
        self.keyboard = SimpleNamespace(press=self.press)
        self.set_viewport_size = AsyncMock()
        self.wait_for_timeout = AsyncMock()
        self.close = AsyncMock()
        self.inner_text = AsyncMock(return_value='Casa en venta Arequipa')

    async def goto(self, url, **kwargs):
        self.url = url
        return SimpleNamespace(status=200)

    async def press(self, _):
        self.round += 1

    def locator(self, _):
        return SimpleNamespace(count=AsyncMock(return_value=0))

    async def content(self):
        return '<title>Casa en venta</title><body>Publicado en Arequipa</body>'

    async def evaluate(self, script, *args):
        if '.outerHTML' in script:
            ids = self.blocks[min(self.round, len(self.blocks)-1)]
            return ''.join(f'<a href="/marketplace/item/{i}/"><span>S/100000</span><span>Casa en venta</span><span>Arequipa</span><img src="https://example.test/photo.jpg" alt="Casa en venta en Arequipa, AR"></a>' for i in ids)
        if 'visibleCards:' in script:
            return {'y': 0, 'height': 900, 'viewport': 900, 'target': 'DIV', 'visibleCards': 24}
        return True


class MarketplaceScrollTests(IsolatedAsyncioTestCase):
    async def crawl(self, blocks, limit=60, *, resume=None, cancel=False, details=False):
        page = FakePage(blocks)
        browser = SimpleNamespace(new_page=AsyncMock(return_value=page),
            cookies=AsyncMock(return_value=[{'name': 'c_user'}]))
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=browser)
        context.__aexit__ = AsyncMock(return_value=False)
        events, saved = [], []
        def progress(payload):
            events.append(payload)
            if cancel and len([e for e in events if e.get('candidate_batch')]) > 1:
                return False
            return True
        def save(rows):
            saved.extend(rows)
            return {'total': len(saved), 'nuevas': len(saved)}
        with ExitStack() as stack:
            stack.enter_context(patch('camoufox.async_api.AsyncCamoufox', return_value=context))
            for name, value in {'camoufox_kwargs': lambda **kw: {}, 'is_headless_server': lambda: True,
                'SESSION_COOKIES_JSON': '', 'MIN_SCROLL_ROUNDS': 2, 'MAX_SCROLL_ROUNDS': 6,
                'DEFAULT_IDLE_SCROLLS': 2, 'upload_image': lambda *a: None}.items():
                stack.enter_context(patch.object(fb, name, value))
            result = await fb.scrape_marketplace(max_items=limit, resume_state=resume,
                discovery_only=not details, progress_callback=progress, batch_callback=save)
        return result, events, saved

    async def test_virtualized_feed_keeps_ids_after_cards_leave_dom(self):
        rows, events, _ = await self.crawl([range(1,25), range(13,37), range(37,61)])
        self.assertEqual({r['id_origen'] for r in rows}, {str(i) for i in range(1,61)})
        persisted = [c['id'] for e in events for c in e.get('candidate_batch', [])]
        self.assertEqual(len(persisted), len(set(persisted)))
        self.assertEqual(len(persisted), 60)
        self.assertEqual(rows.discovery.stop_reason, 'max_items')
        self.assertFalse(rows.discovery.complete)

    async def test_stall_is_partial_even_when_cards_exist(self):
        rows, _, _ = await self.crawl([range(1,25)], limit=100)
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows.discovery.stop_reason, 'stalled')
        self.assertFalse(rows.discovery.complete)

    async def test_delayed_new_batch_resets_idle_counter(self):
        rows, _, _ = await self.crawl([range(1,25), range(1,25), range(25,61)])
        self.assertEqual(len(rows), 60)

    async def test_interruption_during_discovery_aborts_before_details(self):
        with self.assertRaises(ScrapingInterrupted):
            await self.crawl([range(1,25), range(25,49)], cancel=True)

    async def test_resume_skips_saved_ids_instead_of_ordinal(self):
        rows, _, saved = await self.crawl([range(1,4)], limit=3, details=True,
            resume={'saved_ids': ['1'], 'candidates': []})
        self.assertEqual([r['id_origen'] for r in saved], ['2', '3'])
        self.assertEqual(len(rows), 2)

    async def test_scroll_limit_is_not_end_of_feed(self):
        rows, _, _ = await self.crawl([range(n*24+1,n*24+25) for n in range(9)], limit=1000)
        self.assertEqual(rows.discovery.stop_reason, 'max_scroll_rounds')
        self.assertGreater(len(rows), 24)
        self.assertFalse(rows.discovery.complete)
