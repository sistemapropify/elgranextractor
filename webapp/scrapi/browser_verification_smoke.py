"""Offline Camoufox check: a delayed ordinary control reaches the remote image.

All requests are intercepted; this does not visit a portal or solve a CAPTCHA.
"""
import asyncio
import json
import time
from unittest.mock import patch

from camoufox.async_api import AsyncCamoufox

from .browser_verification import BROWSER_TIMEOUT_SECONDS, _perform_user_click, resolve
from .camoufox_launcher import manual_pointer_kwargs
from .contracts import ScrapingInterrupted


async def check_pointer(browser):
    """Use the manual-input production launcher on an offline checkbox."""
    page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
    requests = []
    async def fixture(route):
        requests.append(route.request.url)
        await route.fulfill(content_type='text/html', body='''<!doctype html>
            <title>Ordinary pointer test</title><input type="checkbox" id="test"
            style="position:absolute;left:290px;top:190px;width:20px;height:20px">
            <script>document.querySelector('input').dataset.clickCount = '0';
            document.querySelector('input').addEventListener('click', event => {
                event.target.dataset.clickCount = String(Number(event.target.dataset.clickCount) + 1);
            });
            </script>''')
    await page.route('**/*', fixture)
    await page.goto('https://example.test/offline-checkbox')
    print('Ordinary offline checkbox loaded', flush=True)
    timings = []
    try:
        for _ in range(3):
            await page.locator('#test').evaluate('element => element.checked = false')
            await asyncio.wait_for(page.mouse.move(30, 30), BROWSER_TIMEOUT_SECONDS)
            started = time.monotonic()
            await asyncio.wait_for(_perform_user_click(page, 300, 200), BROWSER_TIMEOUT_SECONDS)
            timings.append(round(time.monotonic() - started, 3))
            assert await page.locator('#test').is_checked(), 'Ordinary checkbox did not receive click'
            print('Ordinary checkbox click completed:', timings[-1], flush=True)
        assert await page.locator('#test').get_attribute('data-click-count') == '3', 'Duplicate or missing clicks'
        assert len(requests) == 1, requests
        return timings
    finally:
        await page.close()


async def check_cross_origin_pointer(browser):
    """Native input must reach an ordinary closed-shadow cross-origin frame.

    COOP/COEP force the frame boundary missing from the old top-level test.
    Both origins are local routed fixtures, with no challenge or external IO.
    """
    context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = await context.new_page()
    requests = []

    async def fixture(route):
        requests.append(route.request.url)
        if route.request.url.startswith('https://frame.test/'):
            body = '''<body style="margin:0"><input id="test" type="checkbox"
                style="position:absolute;left:10px;top:24px;width:22px;height:22px;margin:0">
                <script>document.querySelector('input').addEventListener('click', e =>
                parent.postMessage({checked:e.target.checked}, 'https://parent.test'))</script>'''
        else:
            body = '''<div id="host" style="position:absolute;left:272px;top:304px;width:896px;height:68px"></div>
                <script>const root=document.querySelector('#host').attachShadow({mode:'closed'});
                root.innerHTML='<iframe src="https://frame.test/control" style="border:0;width:896px;height:68px"></iframe>';
                window.addEventListener('message', e => {if(e.origin==='https://frame.test')
                document.body.dataset.checked=String(e.data.checked)});</script>'''
        await route.fulfill(content_type='text/html', body=body, headers={
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Resource-Policy': 'cross-origin',
        })

    try:
        await context.route('**/*', fixture)
        async with page.expect_event('framenavigated',
                                     predicate=lambda frame: frame.url == 'https://frame.test/control',
                                     timeout=10000):
            await page.goto('https://parent.test/control')
        await page.frame(url='https://frame.test/control').locator('#test').wait_for()
        await asyncio.wait_for(_perform_user_click(page, 293, 338), BROWSER_TIMEOUT_SECONDS)
        await page.locator('body[data-checked="true"]').wait_for(state='attached', timeout=3000)
        assert requests == ['https://parent.test/control', 'https://frame.test/control'], requests
        print('Closed-shadow cross-origin ordinary checkbox received the native click', flush=True)
    finally:
        await context.close()


async def main():
    print('Starting offline verification smoke', flush=True)
    options = await asyncio.to_thread(manual_pointer_kwargs)
    async with AsyncCamoufox(**options) as browser:
        timings = await check_pointer(browser)
        await check_cross_origin_pointer(browser)
        print('Ordinary pointer check passed; checking screenshot refresh', flush=True)
        page = await browser.new_page()
        requests, navigations, screenshots, events = [], [], [], []
        async def fixture(route):
            requests.append(route.request.url)
            await route.fulfill(content_type='text/html', body='''<!doctype html>
                <title>Just a moment - offline test</title>
                <h1>Loading a local test control</h1><div id="control"></div>''')
        await page.route('**/*', fixture)
        page.on('framenavigated', lambda frame: navigations.append(frame.url))
        # The hostname is only used to exercise the resolver's domain guard;
        # routing above supplies an isolated document with no external assets.
        await page.goto('https://www.adondevivir.com/verification-offline-test')
        page._scraping_document_status = 403
        opened = asyncio.Event()
        loop = asyncio.get_running_loop()

        def exchange(action, **payload):
            if action == 'open':
                screenshots.append(payload['screenshot'])
                loop.call_soon_threadsafe(opened.set)
                return 'initial'
            if action == 'refresh':
                screenshots.append(payload['screenshot'])
                return 'refreshed'
            if action == 'poll' and payload['id'] == 'refreshed':
                raise ScrapingInterrupted('offline test complete')

        async def reveal_control():
            await opened.wait()
            await page.locator('#control').evaluate('''element => {
                element.innerHTML = '<label><input type="checkbox"> Ordinary test checkbox</label>';
            }''')

        async def emit(**payload):
            events.append(payload.get('event'))

        reveal = asyncio.create_task(reveal_control())
        try:
            with patch('scrapi.browser_verification.SCREEN_REFRESH_SECONDS', .2):
                try:
                    await asyncio.wait_for(resolve(page, exchange, emit), 60)
                except ScrapingInterrupted as exc:
                    assert str(exc) == 'offline test complete', str(exc)
            await reveal
            assert await page.locator('input[type=checkbox]').count() == 1
            assert not await page.locator('input[type=checkbox]').is_checked()
            assert len(screenshots) == 2 and screenshots[0] != screenshots[1]
            assert 'verification.screen_refreshed' in events
            assert 'verification.completed' not in events
            assert len(navigations) == 1, navigations
            assert len(requests) == 1, requests
            print(json.dumps({'result': 'passed', 'automatic_captures': len(screenshots),
                              'navigations': len(navigations), 'control_clicked': False,
                              'ordinary_checkbox_click_seconds': timings}))
        finally:
            if not reveal.done():
                reveal.cancel()
            await asyncio.gather(reveal, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
