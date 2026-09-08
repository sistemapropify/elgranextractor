"""Real browser launch/close test; also runs with Docker --network none."""
import asyncio
import importlib.metadata
import json
import platform
import subprocess
import os
from pathlib import Path


async def smoke():
    from camoufox.async_api import AsyncCamoufox
    from .camoufox_launcher import camoufox_kwargs
    binary = os.environ.get('CAMOUFOX_EXECUTABLE_PATH')
    if binary and platform.system() == 'Linux':
        dependencies = subprocess.run(['ldd', binary], capture_output=True, text=True, timeout=20, check=True)
        if 'not found' in dependencies.stdout:
            raise RuntimeError('runtime.dependency_missing: ' + dependencies.stdout)
    options = await asyncio.to_thread(camoufox_kwargs, headless=True, timeout=120000)
    async with AsyncCamoufox(**options) as browser:
        page = await browser.new_page()
        await page.goto('data:text/html,<title>scraping-ready</title><p id="ready">OK</p>')
        assert await page.title() == 'scraping-ready'
        assert await page.locator('#ready').inner_text() == 'OK'
        from .paged_engine import PAGINATION_JS
        for html, expected in (
            ('<div class="pagination"><button>Primera</button><span>Página 32 de 34</span><button>Última</button></div>', {'current': 32, 'total_pages': 34}),
            ('<div class="Pagination"><a>Anterior</a><span>33</span></div>', {'pager_present': True, 'next_present': False}),
            ('<a data-qa="PAGING_NEXT" aria-disabled="true">Siguiente</a>', {'next_present': True, 'next_enabled': False}),
        ):
            await page.set_content(html)
            state = await page.evaluate(PAGINATION_JS)
            for key, value in expected.items():
                assert state[key] == value, (key, state)
        version = browser.version
    return {'event': 'runtime.ready', 'python': platform.python_version(), 'browser': version,
            'camoufox': importlib.metadata.version('camoufox'),
            'playwright': importlib.metadata.version('playwright'),
            'revision': os.environ.get('SCRAPING_REVISION', 'development')}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(asyncio.wait_for(smoke(), timeout=180))), flush=True)
