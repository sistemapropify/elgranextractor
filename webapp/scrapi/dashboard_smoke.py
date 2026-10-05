"""Exercise the actual dashboard fragment in a browser with isolated HTTP fixtures."""
import asyncio
import base64
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from django.conf import settings
from django.template import Context, Engine
from camoufox.async_api import AsyncCamoufox
from .camoufox_launcher import camoufox_kwargs
from .source_config import DEFAULT_URLS


async def main():
    if not settings.configured:
        settings.configure(USE_I18N=False, USE_TZ=True)
    template = (Path(__file__).resolve().parents[1] / 'templates/ingestas/scraping_dashboard.html').read_text(encoding='utf-8')
    # Test this module's real blocks independently from unrelated application navigation.
    template = re.sub(r'{%\s*(?:extends\s+[^%]+|load\s+[^%]+|block\s+[^%]+|endblock)\s*%}', '', template)
    html = '<!doctype html><html><meta charset="utf-8"><body>' + Engine().from_string(template).render(Context({
        'csrf_token': 'isolated-test-token', 'urls_portales': DEFAULT_URLS,
        'stats_por_portal': {}, 'total_propiedades': 0,
        'worker_health': {'ready': True, 'message': 'Worker disponible'},
    })) + '</body></html>'
    requests, errors = [], []
    control_connection_failed = False
    verification_fixture = None
    executed_screenshot = None
    async def respond(route):
        request = route.request
        parts = urlsplit(request.url)
        requests.append({'path': parts.path, 'query': parse_qs(parts.query), 'body': request.post_data or ''})
        if parts.path == '/':
            await route.fulfill(content_type='text/html', body=html)
            return
        if '/verificacion/' in parts.path:
            if request.method == 'POST':
                verification_fixture.update(state='executed', screenshot=executed_screenshot)
                data = {'success': True}
            else:
                data = {'verification': verification_fixture}
        elif '/control/' in parts.path:
            if control_connection_failed:
                await route.abort('internetdisconnected')
                return
            data = {'success': True, 'job_id': 42, 'estado': 'running'}
        elif '/stream/' in parts.path:
            data = {'logs': [{'id': 1, 'nivel': 'warning', 'mensaje': '<img src=x onerror=alert(1)>',
                'portal': 'urbania', 'propiedad_id': '123', 'evento': 'detail.failed', 'contexto': {},
                'timestamp': '2026-09-08T00:00:00Z'}],
                'last_id': 1, 'ended': True, 'estado': 'error', 'has_more': False}
        elif '/status/' in parts.path:
            data = {'estado': 'error', 'detectadas': 30, 'portales': [{'nombre': 'Urbania',
                'source': {'source_url': DEFAULT_URLS['urbania']},
                'discovery': {'unique_ids': 30, 'stop_reason': 'max_pages'}, 'pending': 1}]}
        else:
            await route.fulfill(content_type='text/html', body='<table><tbody></tbody></table>')
            return
        await route.fulfill(content_type='application/json', body=json.dumps(data))
    # This fixture tests dashboard behavior, not generated cursor paths. The
    # pinned Linux browser can stall on intermediate humanization events;
    # use real native clicks without that unrelated randomized input layer.
    options = await asyncio.to_thread(camoufox_kwargs, humanize=False)
    async with AsyncCamoufox(**options) as browser:
        page = await browser.new_page()
        await page.route('**/*', respond)
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://scraping.test/')
        await page.locator('.url-input').first.wait_for()
        assert await page.locator('.url-input').count() == 5
        # Exercise a real offline/online transition in the browser. A click
        # while offline must not become a delayed job submission on reconnect.
        await page.context.set_offline(True)
        await page.locator('#terminalBody').get_by_text('Sin conexión a internet:', exact=False).wait_for()
        await page.locator('#btnStart').click()
        await page.locator('#terminalBody').get_by_text('La acción no se envió:', exact=False).wait_for()
        assert not any('/control/' in r['path'] for r in requests)
        assert await page.locator('#terminalBody').get_by_text('Sin conexión a internet:', exact=False).count() == 1
        await page.context.set_offline(False)
        await page.locator('#terminalBody').get_by_text('El navegador vuelve a detectar conexión.', exact=False).wait_for()
        assert not any('/control/' in r['path'] for r in requests)

        # A failed request while the network adapter is online has an unknown
        # cause: do not claim that the user definitely lost internet access.
        control_connection_failed = True
        await page.locator('#btnStart').click()
        await page.locator('#terminalBody').get_by_text('No se pudo contactar con el servidor.', exact=False).wait_for()
        control_connection_failed = False
        await page.locator('#btnPreview').click()
        await page.locator('#runCoverage').get_by_text('30 IDs', exact=False).wait_for()
        assert await page.locator('#terminalBody img').count() == 0
        assert 'onerror' in await page.locator('#terminalBody').inner_text()
        await page.locator('#logEvent').fill('detail.failed')
        await page.locator('#logProperty').fill('123')
        await page.locator('#logProperty').dispatch_event('change')
        await page.wait_for_function("document.querySelector('#terminalBody').textContent.includes('onerror')")
        async with page.expect_response(lambda response: '/control/' in response.url
                                        and 'resume' in (response.request.post_data or '')):
            await page.locator('#btnResume').click()
        assert any('preview' in r['body'] and 'isolated-test-token' in r['body'] for r in requests)
        assert any(r['query'].get('evento') == ['detail.failed'] and r['query'].get('propiedad_id') == ['123'] for r in requests)
        assert any('resume' in r['body'] for r in requests)

        # Ordinary-control screenshots, not a portal or CAPTCHA. The same
        # executed action ID must display a new image without enabling replay.
        image_page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        await image_page.set_content('<input type="checkbox" id="ordinary">')
        initial_screenshot = base64.b64encode(await image_page.screenshot()).decode('ascii')
        await image_page.locator('#ordinary').check()
        executed_screenshot = base64.b64encode(await image_page.screenshot()).decode('ascii')
        assert initial_screenshot != executed_screenshot
        await image_page.close()
        verification_fixture = {'id': 'ordinary-screen', 'state': 'waiting', 'mode': 'browser',
                                'expires_at': '2099-01-01T00:00:00Z', 'screenshot': initial_screenshot}
        await page.locator('#btnStart').click()
        await page.locator('#verificationImage').wait_for(state='visible')
        await page.wait_for_function('document.querySelector("#verificationImage").naturalWidth > 0')
        await page.locator('#verificationImage').click(position={'x': 20, 'y': 20})
        await page.wait_for_function('(src) => document.querySelector("#verificationImage").getAttribute("src") === src',
                                     arg='data:image/png;base64,' + executed_screenshot, timeout=10000)
        assert verification_fixture['id'] == 'ordinary-screen'
        sent = len([r for r in requests if '/verificacion/' in r['path'] and 'answer' in r['body']])
        await page.locator('#verificationImage').click(position={'x': 20, 'y': 20})
        assert len([r for r in requests if '/verificacion/' in r['path'] and 'answer' in r['body']]) == sent == 1
        assert not errors, errors
        await page.close()
    print(json.dumps({'dashboard': 'passed', 'checks': ['offline', 'online', 'no_action_replay', 'network_error', 'preview', 'csrf', 'five_urls', 'coverage', 'text_only_logs', 'filters', 'resume', 'post_click_image_update_same_id', 'no_duplicate_click']}))


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=120))
