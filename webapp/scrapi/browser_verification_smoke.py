"""Offline Camoufox check: a delayed ordinary control reaches the remote image.

All requests are intercepted; this does not visit a portal or solve a CAPTCHA.
"""
import asyncio
import json
from unittest.mock import patch

from camoufox.async_api import AsyncCamoufox

from .browser_verification import resolve
from .camoufox_launcher import camoufox_kwargs
from .contracts import ScrapingInterrupted


async def main():
    options = await asyncio.to_thread(camoufox_kwargs)
    async with AsyncCamoufox(**options) as browser:
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
                              'navigations': len(navigations), 'control_clicked': False}))
        finally:
            if not reveal.done():
                reveal.cancel()
            await asyncio.gather(reveal, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
