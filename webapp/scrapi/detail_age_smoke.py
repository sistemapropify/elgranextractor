"""Offline real-browser regression using the inspected Adondevivir template."""
import asyncio
from pathlib import Path
from unittest.mock import patch

from camoufox.async_api import AsyncCamoufox
from scrapi import adondevivir_scraper as adon
from scrapi.camoufox_launcher import camoufox_kwargs
from scrapi.paged_engine import enrich, normalize


async def main():
    fixture = Path(__file__).with_name('fixtures').joinpath('adondevivir_151259141_features.html').read_text(encoding='utf-8')
    url = 'https://www.adondevivir.com/propiedades/clasificado/veclapin-venta-de-departamento-en-yanahuara-151259141.html'
    async with AsyncCamoufox(**camoufox_kwargs(headless=True)) as browser:
        page = await browser.new_page()

        async def navigate(page, url, timeout):
            page._scraping_document_status = 200

        async def render(html):
            await page.unroute('**/*')
            await page.route('**/*', lambda route: route.fulfill(
                status=200, content_type='text/html; charset=utf-8', body=html))
            await page.goto(url)

        for age in (7, 13, 0):
            html = fixture.replace('        7\n        años', f'        {age}\n        años')
            await render(html)
            assert await page.locator('.nf-container .item .label').count() == 0
            raw = {'id': '151259141', 'url': url, 'tipo': 'Departamento'}
            with patch.object(adon, 'navegar_con_cloudflare', side_effect=navigate):
                await enrich('adondevivir', adon, page, raw)
            row = normalize('adondevivir', adon, raw)
            assert row['antiguedad_anios'] == age, row
            assert row['datos_crudos']['_age_evidence']['value'] == f'{age} años'
            assert raw['_detail_area_labels'] == {'total': 62.0, 'covered': 62.0}

        # Do not misclassify advertiser prose when the age chip is absent.
        await render(fixture.replace('<i class="icon-antiguedad"></i>\n        7\n        años', '<i></i>\n        Antigüedad no informada'))
        raw = {'id': '151259141', 'url': url, 'tipo': 'Departamento'}
        with patch.object(adon, 'navegar_con_cloudflare', side_effect=navigate):
            await enrich('adondevivir', adon, page, raw)
        assert normalize('adondevivir', adon, raw)['antiguedad_anios'] is None

        # Older feature template remains supported.
        await render('<html><head><title>Departamento</title></head><body>'
                     '<div class="nf-container"><div class="item"><span class="label">13 años</span></div></div></body></html>')
        assert await page.evaluate(adon.DETAIL_FEATURES_JS) == ['13 años']
    print('PASS actual Adondevivir feature template: age 7, 13, 0; unknown stays null; legacy fallback works')


if __name__ == '__main__':
    asyncio.run(main())
