"""Common discovery, retry and checkpoint policy for paginated portals.

Safety limits are partial outcomes. Empty/challenged/repeated pages never
certify completion. Detail errors leave durable candidates pending.
"""
import asyncio
import importlib
import os
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit

from .contracts import Discovery, ScrapeRows, ScrapingInterrupted
from .normalization import number, operation, property_type, urbania_row, validate_row
from .source_config import page_url, validate_url

PAGINATION_JS = r"""() => {
 const links = [...document.querySelectorAll('a,button')];
 const requestedPage = Number(new URL(location.href).searchParams.get('page') || '1');
 const next = document.querySelector('[data-qa="PAGING_NEXT"]') || links.find(el =>
   /^(siguiente|next|siguiente página|next page)$/i.test((el.innerText || el.getAttribute('aria-label') || '').trim())
   || el.getAttribute('rel') === 'next') || links.find(el => {
      if (!el.closest('.pagination, [class*="pagination"]') || !el.getAttribute('href')) return false;
      const target = new URL(el.getAttribute('href'), location.href);
      return target.pathname === location.pathname && Number(target.searchParams.get('page')) === requestedPage + 1;
   });
 const disabled = el => !!el && (el.disabled || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true'
   || (el.tagName === 'A' && !el.getAttribute('href'))
   || el.classList.contains('disabled') || !!el.closest('[aria-disabled="true"],.disabled'));
 const pager = document.querySelector('[data-qa^="PAGING_"], .pagination, [class*="pagination" i], [aria-label*="aginaci"]')
   || links.find(el=>/^(anterior|previous)$/i.test((el.innerText||'').trim()))?.parentElement;
 const text = document.body.innerText || '';
 const count = text.match(/p[aá]gina\s*(\d+)\s*de\s*(\d+)/i);
 const empty = /(?:no se encontraron|no encontramos|no hay)\s+(?:resultados|propiedades|inmuebles)/i.test(text);
 return {next_present:!!next, next_enabled:!!next && !disabled(next),
   next_href:next?.getAttribute('href') || '', pager_present:!!pager,
   current:count ? Number(count[1]) : null, total_pages:count ? Number(count[2]) : null,
   explicit_empty:empty,
   controls:pager ? [...pager.querySelectorAll('a,button,option')].slice(0,60).map(el=>({text:(el.textContent||'').trim(), href:el.getAttribute('href'), value:el.getAttribute('value')})) : []};
}"""


def stable_id(raw):
    return str(raw.get('ID') or raw.get('id') or '').strip()


def unique_items(items):
    result = {}
    invalid = duplicates = 0
    for raw in items:
        key = stable_id(raw)
        if not key:
            invalid += 1
            continue
        if key in result:
            duplicates += 1
        else:
            result[key] = raw
    return result, invalid, duplicates


def terminal_reason(portal, state):
    if state.get('total_pages'):
        return 'last_page_observed' if state.get('current') == state['total_pages'] else None
    if state.get('next_present') and not state.get('next_enabled'):
        return 'next_disabled'
    if portal != 'remax' and state.get('pager_present') and not state.get('next_present'):
        return 'no_next_control'
    return None


def normalize(portal, source, raw):
    stamp = datetime.now(timezone.utc).isoformat()
    if portal == 'urbania':
        return urbania_row(raw, stamp)
    mapped = source.mapear_a_formato_remax(raw) if portal != 'remax' else raw
    row = source.estandarizar(mapped, stamp)
    row['fuente'] = portal
    row['datos_crudos'] = dict(raw)
    text = ' '.join(str(raw.get(k) or '') for k in ('tipo', 'Tipo', 'Titulo', 'titulo'))
    kind = property_type(text)
    row['tipo_inmueble'] = kind
    row['tipo_operacion'] = operation(text + ' ' + str(raw.get('_source_url') or ''))
    row['precio_soles'] = number(mapped.get('Precio S/.'))
    row['precio_usd'] = number(mapped.get('Precio USD'))
    if portal == 'adondevivir':
        location = [p.strip() for p in str(raw.get('ubicacion') or '').split(',') if p.strip()]
        row['departamento'] = location[-1] if len(location) >= 3 else None
        row['provincia'] = location[-2] if len(location) >= 3 else (location[-1] if len(location) == 2 else None)
        row['distrito'] = location[0] if location else None
    return validate_row(row)


async def enrich(portal, source, page, raw):
    url = raw.get('URL Propiedad') or raw.get('url')
    if not url:
        raise ValueError('detail.missing_url')
    validate_url(portal, url)
    page._scraping_document_status = None
    raw.pop('_detail_error', None)
    if portal == 'adondevivir':
        lat, lng, kind, image = await source.extraer_coordenadas_desde_detalle(page, url)
        raw.update(latitud=lat, longitud=lng)
        if kind:
            raw['tipo'] = kind
        if image:
            raw['imagen_url'] = image
    else:
        await source.extraer_detalle(page, raw)
    validate_url(portal, page.url)
    status = getattr(page, '_scraping_document_status', None)
    if status is None or status >= 400:
        raise RuntimeError(f'detail.http_error: HTTP {status}')
    if urlsplit(page.url).path.rstrip('/') != urlsplit(url).path.rstrip('/'):
        raise RuntimeError('detail.unexpected_redirect: no se cargó la ficha solicitada')
    title = (await page.title()).lower()
    if not title.strip():
        raise RuntimeError('detail.not_ready: la ficha no terminó de cargar')
    if any(marker in title for marker in ('just a moment', 'access denied', 'attention required')):
        raise RuntimeError('detail.blocked: la ficha no superó la página de acceso')


async def guarded_navigation(page, portal):
    def response_received(response):
        if response.request.resource_type == 'document' and response.frame == page.main_frame:
            page._scraping_document_status = response.status
    page.on('response', response_received)
    async def guard(route):
        request = route.request
        if request.is_navigation_request() and request.frame == page.main_frame:
            try:
                validate_url(portal, request.url)
            except ValueError:
                await route.abort('blockedbyclient')
                return
        await route.continue_()
    await page.route('**/*', guard)


async def prepare_detail(portal, source, page, raw, emit, *, store_images=False):
    """Use the same bounded retries, normalization and images on initial/resumed work."""
    key = stable_id(raw)
    for attempt in range(1, 4):
        try:
            await emit(event='detail.started', property_id=key, attempt=attempt,
                       message=f'{portal}: abriendo ficha {key}')
            await asyncio.wait_for(enrich(portal, source, page, raw), timeout=100)
            row = normalize(portal, source, raw)
            break
        except ScrapingInterrupted:
            raise
        except Exception as exc:
            await emit(event='detail.retry' if attempt < 3 else 'detail.failed',
                       level='warning' if attempt < 3 else 'error', property_id=key,
                       attempt=attempt, error_type=type(exc).__name__,
                       message=f'{type(exc).__name__}: {exc or "se agotó el tiempo de respuesta"}')
            if attempt == 3:
                raise
            await asyncio.sleep(attempt * 2)
    if portal in ('adondevivir', 'properati') and store_images and row.get('imagen_url'):
        try:
            blob_image = await asyncio.wait_for(asyncio.to_thread(
                source.subir_imagen_a_blob, row['imagen_url'], raw), timeout=60)
        except Exception as exc:
            blob_image = None
            await emit(event='image.failed', level='warning', property_id=key,
                       error_type=type(exc).__name__, message=str(exc))
        if blob_image:
            row['imagen_url'] = blob_image
        await emit(event='image.saved' if blob_image else 'image.failed',
                   level='info' if blob_image else 'warning', property_id=key,
                   message=f'{portal}: imagen {"almacenada" if blob_image else "no almacenada; URL original conservada"}')
    await emit(event='detail.extracted', property_id=key, effective_url=page.url,
               message=f'{portal}: ficha {key} analizada',
               fields_present=[k for k, v in row.items() if v is not None and k != 'datos_crudos'],
               quality_issues=(row.get('datos_crudos') or {}).get('_quality_issues', []))
    return row


async def navigate(page, source, portal, url, emit):
    for attempt in range(1, 4):
        await emit(event='navigation.started', message=f'{portal}: abriendo listado',
                   requested_url=url, attempt=attempt)
        start = time.monotonic()
        try:
            page._scraping_document_status = None
            response = await page.goto(validate_url(portal, url), wait_until='domcontentloaded', timeout=60000)
            status = response.status if response else None
            validate_url(portal, page.url)
            ready = await source.esperar_cloudflare(page, timeout=30)
            if ready is False:
                raise RuntimeError('navigation.blocked: acceso pendiente')
            status = getattr(page, '_scraping_document_status', None) or status
            if status is None or status >= 400:
                raise RuntimeError(f'navigation.http_error: HTTP {status}')
            await page.wait_for_timeout(1500)
            await emit(event='navigation.loaded', message=f'{portal}: listado cargado',
                       requested_url=url, effective_url=page.url, http_status=status,
                       duration_ms=int((time.monotonic()-start)*1000), attempt=attempt)
            return
        except ScrapingInterrupted:
            raise
        except Exception as exc:
            await emit(event='navigation.failed', level='error', message=str(exc),
                       requested_url=url, attempt=attempt, error_type=type(exc).__name__)
            if attempt == 3:
                raise
            await asyncio.sleep(attempt * 2)


async def crawl_pages(portal, source_url, source, page, detail_page, *, emit,
                      batch_callback=None, start_page=1, max_pages=300,
                      known_ids=(), saved_ids=(), failed_ids=(), discovery=None,
                      listing_only=False):
    result = ScrapeRows(discovery=discovery)
    stats = result.discovery
    seen = set(known_ids)
    saved = set(saved_ids)
    failed = set(failed_ids)
    signatures = set()
    next_url = page_url(portal, source_url, start_page)
    for n in range(max(1, start_page), max_pages + 1):
        await navigate(page, source, portal, next_url, emit)
        props = await source.extraer_listado(page)
        unique, invalid, duplicates = unique_items(props)
        for raw in unique.values():
            raw['_source_url'] = source_url
        state = await page.evaluate(PAGINATION_JS)
        stats.final_url = page.url
        signature = tuple(sorted(unique))
        effective_number = parse_qs(urlsplit(page.url).query).get('page', [str(n)])[0]
        if not unique:
            stats.stop_reason = 'empty_confirmed' if state['explicit_empty'] else 'empty_unexpected'
            # Only a documented empty initial search can certify zero results.
            stats.complete = bool(state['explicit_empty'] and n == 1 and not seen)
            break
        if (signature in signatures or (state['current'] and state['current'] < n)
                or (portal in ('urbania', 'remax') and effective_number.isdigit() and int(effective_number) < n)):
            stats.stop_reason = 'repeated_page'
            break
        signatures.add(signature)
        stats.pages += 1
        stats.invalid += invalid
        stats.duplicates += duplicates + len(set(unique) & seen)
        seen.update(unique)
        stats.unique_ids = len(seen)
        await emit(event='listing.discovered', message=f'{portal}: página {n}, {len(unique)} IDs válidos',
                   page=n, raw_rows=len(props), unique_ids=len(unique), total_unique=len(seen),
                   missing_id=invalid, duplicates=stats.duplicates,
                   pagination=state,
                   candidate_batch=[{'id': key, 'raw': raw, 'page': n} for key, raw in unique.items()])
        for key, raw in unique.items():
            if key in saved:
                continue
            if not listing_only:
                try:
                    row = await prepare_detail(portal, source, detail_page, raw, emit,
                                               store_images=bool(batch_callback))
                    failed.discard(key)
                except ScrapingInterrupted:
                    raise
                except Exception as exc:
                    failed.add(key)
                    raw['_detail_error'] = str(exc)[:1000]
                    await emit(event='detail.failed', level='error', message=str(exc),
                               page=n, property_id=key, candidate_error={'id': key, 'error': str(exc)})
                    continue
            else:
                row = normalize(portal, source, raw)
            if batch_callback:
                counters = await asyncio.to_thread(batch_callback, [row])
                await emit(event='persistence.saved', message=f'{portal}: ficha {key} guardada',
                           page=n, property_id=key, processed=counters.get('total'),
                           nuevas=counters.get('nuevas'), actualizadas=counters.get('actualizadas'),
                           errores=counters.get('errores'))
            result.append(row)
            saved.add(key)
        stats.details_failed = len(failed)
        terminal = terminal_reason(portal, state)
        if terminal:
            stats.stop_reason, stats.complete = terminal, not stats.invalid
        if not failed:
            await emit(event='checkpoint.confirmed', message=f'{portal}: página {n} guardada',
                       checkpoint_page=n, page=n, discovery=stats.as_dict())
        else:
            await emit(event='checkpoint.pending', level='warning', page=n,
                       message=f'{portal}: {len(failed)} fichas pendientes; descubrimiento conservado',
                       discovery=stats.as_dict())
        if terminal:
            break
        if state['next_href'] and portal in ('properati', 'adondevivir'):
            next_url = validate_url(portal, urljoin(page.url, state['next_href']))
        else:
            next_url = page_url(portal, source_url, n + 1)
    else:
        stats.stop_reason = 'max_pages'
    stats.details_failed = len(failed)
    if stats.invalid:
        stats.complete = False
    await emit(event='discovery.finished', level='info' if stats.complete else 'warning',
               message=f'{portal}: recorrido terminado ({stats.stop_reason}), {stats.unique_ids} IDs',
               discovery=stats.as_dict())
    return result


def run_paged(portal, *, source_url, max_paginas=0, start_page=1,
              progress_callback=None, batch_callback=None, resume_state=None,
              listing_only=False):
    source = importlib.import_module(f'scrapi.{portal}_scraper')
    state = resume_state or {}

    async def emit(**payload):
        if progress_callback and await asyncio.to_thread(progress_callback, payload) is False:
            raise ScrapingInterrupted('Trabajo detenido o reemplazado')
        return True

    async def run():
        from camoufox.async_api import AsyncCamoufox
        from .camoufox_launcher import camoufox_kwargs
        # preflight is bounded internally; run it off the async event loop.
        options = await asyncio.to_thread(camoufox_kwargs,
            timeout=int(os.environ.get('CAMOUFOX_LAUNCH_TIMEOUT', '120')) * 1000,
            _progress_callback=lambda message: progress_callback and progress_callback({
                'event': 'runtime.preflight', 'message': message}))
        async with AsyncCamoufox(**options) as browser:
            page, detail_page = await browser.new_page(), await browser.new_page()
            await guarded_navigation(page, portal)
            await guarded_navigation(detail_page, portal)
            await page.set_viewport_size({'width': 1440, 'height': 1000})
            # One permanently unavailable detail must not starve the remaining queue.
            failed = set()
            recovered = []
            for candidate in state.get('pending', []):
                raw = dict(candidate['raw'])
                await emit(event='detail.resuming', property_id=candidate['id'],
                           message=f'{portal}: reanudando ficha {candidate["id"]}')
                try:
                    row = await prepare_detail(portal, source, detail_page, raw, emit,
                                               store_images=bool(batch_callback))
                except ScrapingInterrupted:
                    raise
                except Exception as exc:
                    failed.add(candidate['id'])
                    await emit(event='detail.failed', level='error', property_id=candidate['id'],
                               message=str(exc), candidate_error={'id': candidate['id'], 'error': str(exc)})
                    continue
                if batch_callback:
                    counters = await asyncio.to_thread(batch_callback, [row])
                    await emit(event='persistence.saved', property_id=candidate['id'],
                               processed=counters.get('total'), message=f'{portal}: ficha recuperada y guardada')
                recovered.append(row)
                state.setdefault('saved_ids', []).append(candidate['id'])
            previous = state.get('discovery') or {}
            if previous.get('complete') is True:
                # The final page and its evidence were committed before a crash.
                restored = Discovery(**{k: v for k, v in previous.items() if k in Discovery.__dataclass_fields__})
                restored.details_failed = len(failed)
                await emit(event='discovery.resumed', message=f'{portal}: recorrido previo confirmado; {len(failed)} fichas pendientes',
                           discovery=restored.as_dict())
                return ScrapeRows(recovered, discovery=restored)
            rows = await crawl_pages(portal, source_url, source, page, detail_page,
                emit=emit, batch_callback=batch_callback, start_page=start_page,
                max_pages=int(max_paginas or os.environ.get('SCRAPING_MAX_PAGES', '300')),
                known_ids=state.get('known_ids', []), saved_ids=state.get('saved_ids', []),
                failed_ids=failed, listing_only=listing_only,
                discovery=Discovery(invalid=int(previous.get('invalid', 0)),
                                    pages=int(previous.get('pages', 0)),
                                    duplicates=int(previous.get('duplicates', 0))))
            rows[:0] = recovered
            return rows

    try:
        return asyncio.run(asyncio.wait_for(run(), timeout=int(os.environ.get('CAMOUFOX_TOTAL_TIMEOUT', '10800'))))
    except TimeoutError as exc:
        raise RuntimeError(f'{portal}: timeout; recorrido incompleto, candidatos conservados') from exc
