"""Archive the rendered listing after expanding content and loading its map."""
import asyncio
import hashlib
import re
from datetime import datetime, timezone

from .contracts import ScrapingInterrupted
from .source_config import validate_url

CAPTURE_KEY = '_publication_capture'
MAX_HEIGHT = 24000
MAP_ROOTS = {
    'properati': '#location-map',
    'remax': '#map_property',
    'urbania': '#map-section, #article-map',
    'adondevivir': '#map-section, #article-map, #mapContainer, #map',
    'facebook_marketplace': '[data-publication-capture-root]',
}
MAP_BUTTON = re.compile(r'^(?:ver|mostrar|see|show)\s+(?:(?:en|el|on|the)\s+)*(?:mapa|map)(?:\s+de\s+ubicaci[oó]n)?$', re.I)
EXPAND_BUTTON = re.compile(r'^(?:ver m[aá]s|leer m[aá]s|leer descripci[oó]n completa|ver descripci[oó]n completa|see more)$', re.I)

MAP_STATE_JS = r"""selector => {
 const roots = [...document.querySelectorAll(selector)];
 const visible = el => {const r=el.getBoundingClientRect();return r.width>0 && r.height>0 && getComputedStyle(el).visibility!=='hidden'};
 return roots.some(root => [...root.querySelectorAll('canvas, .leaflet-tile-loaded, iframe, img')].some(el =>
  visible(el) && (el.tagName==='CANVAS' ? el.width>0 && el.height>0 :
   el.tagName==='IMG' ? el.complete && el.naturalWidth>0 && /map|tile/i.test(el.src+' '+el.className) :
   el.tagName==='IFRAME' && /maps|mapbox|openstreetmap/i.test(el.src))));
}"""

SCROLL_JS = r"""() => {
 const root=document.scrollingElement;
 const before=root.scrollTop;
 root.scrollTo({top:Math.min(root.scrollHeight,root.scrollTop+Math.max(500,innerHeight*.8)),behavior:'instant'});
 return {height:root.scrollHeight,bottom:root.scrollTop+innerHeight>=root.scrollHeight-3,before};
}"""

MARKETPLACE_LAYOUT_JS = r"""action => {
 if(action==='restore') {
  for(const [el,style] of window.__publicationCaptureStyles || []) {
   if(style===null)el.removeAttribute('style');else el.setAttribute('style',style);
   el.removeAttribute('data-publication-capture-root');
  }
  delete window.__publicationCaptureStyles;return;
 }
 const root=[...document.querySelectorAll('[role="main"], [role="dialog"]')].find(el =>
  el.getBoundingClientRect().width>0 && /descripci[oó]n|description|detalles/i.test(el.innerText));
 if(!root)return false;
 const saved=new Map();const save=el=>{if(!saved.has(el))saved.set(el,el.getAttribute('style'))};
 save(root);root.setAttribute('data-publication-capture-root','');
 for(const el of [root,...root.querySelectorAll('div')]) {
  const s=getComputedStyle(el);
  if(el.scrollHeight>el.clientHeight+100 && /(auto|scroll)/.test(s.overflowY)) {
   save(el);el.style.setProperty('height','auto','important');
   el.style.setProperty('max-height','none','important');el.style.setProperty('overflow','visible','important');
  }
 }
 for(let el=root;el && el!==document.body;el=el.parentElement) {
  save(el);el.style.setProperty('max-height','none','important');
  el.style.setProperty('height','auto','important');el.style.setProperty('overflow','visible','important');
  if(getComputedStyle(el).position==='fixed')el.style.setProperty('position','relative','important');
 }
 window.__publicationCaptureStyles=[...saved];return true;
}"""


def capture_metadata(raw):
    value = (raw or {}).get(CAPTURE_KEY) if isinstance(raw, dict) else None
    return value if isinstance(value, dict) else {}


def preserve_capture(new_raw, old_raw):
    raw = dict(new_raw or {})
    previous = capture_metadata(old_raw)
    if not capture_metadata(raw).get('url') and previous.get('url'):
        raw[CAPTURE_KEY] = dict(previous)
    return raw


async def _report(emit, **event):
    if await emit(**event) is False:
        raise ScrapingInterrupted()


async def _safe_click(locator):
    if not await locator.is_visible():
        return False
    # Inline map controls are allowed; a link to a maps provider leaves the listing.
    allowed = await locator.evaluate("el => !el.closest('a[href]:not([href^=\"#\"])') && !el.closest('form')")
    if not allowed:
        return False
    await locator.click(timeout=2500)
    return True


async def prepare_publication(page, portal, emit, property_id):
    for control in (await page.get_by_text(EXPAND_BUTTON, exact=True).all())[:6]:
        try:
            await _safe_click(control)
        except Exception:
            pass
    # Traverse lazy sections before looking for controls that appear on scroll.
    complete = False
    for step in range(40):
        state = await page.evaluate(SCROLL_JS)
        await page.wait_for_timeout(200)
        if step % 5 == 0:
            await _report(emit,event='capture.scrolling', property_id=property_id,
                       message=f'{portal}: cargando la publicación para su captura')
        if state['height'] > MAX_HEIGHT:
            break
        if state['bottom']:
            # Some pages insert their map/recommendations after reaching the bottom.
            await page.wait_for_timeout(300)
            state = await page.evaluate('() => ({bottom:scrollY+innerHeight>=document.documentElement.scrollHeight-3})')
            if state['bottom']:
                complete = True
                break
    selector = MAP_ROOTS[portal]
    already_visible = await page.evaluate(MAP_STATE_JS, selector)
    if not already_visible:
        for control in (await page.get_by_text(MAP_BUTTON, exact=True).all())[:4]:
            try:
                if await _safe_click(control):
                    await _report(emit, event='capture.map_opened', property_id=property_id,
                                  message=f'{portal}: mapa abierto antes de capturar')
                    validate_url(portal, page.url)
            except ScrapingInterrupted:
                raise
            except Exception:
                pass
    roots = page.locator(selector)
    if await roots.count():
        try:
            await roots.first.scroll_into_view_if_needed(timeout=2500)
        except Exception:
            pass
    loaded = False
    for _ in range(8):
        loaded = await page.evaluate(MAP_STATE_JS, selector)
        if loaded:
            await page.wait_for_timeout(600)
            break
        if not await roots.count():
            break
        await page.wait_for_timeout(400)
    map_status = 'visible' if loaded else 'unavailable'
    if not loaded:
        await _report(emit,event='capture.map_unavailable', level='warning', property_id=property_id,
                   message=f'{portal}: captura con advertencia; el mapa no está disponible o no cargó')
    await page.evaluate("() => window.scrollTo({top:0,behavior:'instant'})")
    await page.wait_for_timeout(200)
    return {'scroll_complete': complete, 'map_status': map_status}


async def capture_publication(row, page, portal, emit):
    """A failed archive never loses the property or an earlier successful capture."""
    key = row['id_origen']
    await _report(emit,event='capture.started', property_id=key,
               message=f'{portal}: preparando captura completa de la publicación')
    marketplace_layout = False
    try:
        validate_url(portal, page.url)
        title = (await page.title()).lower()
        if any(word in title for word in ('just a moment', 'un momento', 'access denied', 'attention required')):
            raise ValueError('capture.blocked')
        if portal == 'facebook_marketplace':
            marketplace_layout = await page.evaluate(MARKETPLACE_LAYOUT_JS, 'prepare')
            if not marketplace_layout:
                raise ValueError('capture.publication_root_missing')
        info = await prepare_publication(page, portal, emit, key)
        validate_url(portal, page.url)
        if portal == 'facebook_marketplace':
            # Capture only the public listing, excluding account navigation and chats.
            target = page.locator('[data-publication-capture-root]')
            bounds = await target.bounding_box()
            if not bounds or bounds['height'] > MAX_HEIGHT:
                raise ValueError('capture.page_too_large')
            content = await target.screenshot(type='jpeg', quality=82, timeout=15000)
        else:
            bounds = await page.evaluate('() => ({width:innerWidth,height:document.documentElement.scrollHeight})')
            if bounds['height'] > MAX_HEIGHT or bounds['width'] * bounds['height'] > 40000000:
                raise ValueError('capture.page_too_large')
            content = await page.screenshot(full_page=True, type='jpeg', quality=82, timeout=15000)
        if len(content) > 20 * 1024 * 1024:
            raise ValueError('capture.file_too_large')
        stamp = datetime.now(timezone.utc)
        identity = hashlib.sha256(f'{portal}:{key}'.encode()).hexdigest()[:24]
        digest = hashlib.sha256(content).hexdigest()
        name = f'capturas/{portal}/{identity}/{stamp:%Y/%m/%d}/{stamp:%H%M%S%f}-{digest[:16]}.jpg'
        from captura.azure_storage import upload_bytes
        url = await asyncio.wait_for(asyncio.to_thread(upload_bytes, content,
            blob_name=name, container_name='propiedadesimagenes', content_type='image/jpeg',
            metadata={'fuente':portal,'propiedad':identity,'captured_at':stamp.isoformat(),'sha256':digest}),timeout=40)
        if not url:
            raise ValueError('capture.upload_failed')
        row.setdefault('datos_crudos', {})[CAPTURE_KEY] = {
            'url':url, 'captured_at':stamp.isoformat(), 'source_url':page.url,
            'width':int(bounds['width']), 'height':int(bounds['height']), **info,
        }
        await _report(emit,event='capture.saved', property_id=key,
                   message=f'{portal}: captura de la publicación almacenada en Azure')
    except ScrapingInterrupted:
        raise
    except Exception as exc:
        await _report(emit,event='capture.failed', level='warning', property_id=key,
                   error_type=type(exc).__name__, message=f'{portal}: no se pudo archivar la captura; la ficha se conserva')
    finally:
        if marketplace_layout:
            try:
                await page.evaluate(MARKETPLACE_LAYOUT_JS, 'restore')
            except Exception:
                pass
    return row
