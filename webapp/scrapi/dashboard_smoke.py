"""Exercise the actual dashboard fragment in a browser with isolated HTTP fixtures."""
import asyncio
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
    async def respond(route):
        request = route.request
        parts = urlsplit(request.url)
        requests.append({'path': parts.path, 'query': parse_qs(parts.query), 'body': request.post_data or ''})
        if parts.path == '/':
            await route.fulfill(content_type='text/html', body=html)
            return
        if '/control/' in parts.path:
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
    options = await asyncio.to_thread(camoufox_kwargs)
    async with AsyncCamoufox(**options) as browser:
        page = await browser.new_page()
        await page.route('**/*', respond)
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://scraping.test/')
        await page.locator('.url-input').first.wait_for()
        assert await page.locator('.url-input').count() == 5
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
        assert not errors, errors
        await page.close()
    print(json.dumps({'dashboard': 'passed', 'checks': ['preview', 'csrf', 'five_urls', 'coverage', 'text_only_logs', 'filters', 'resume']}))


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=120))
