import asyncio
import re
import base64
import openpyxl
import signal
import sys
import json
import random
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit
from camoufox.async_api import AsyncCamoufox
from scrapi.camoufox_launcher import camoufox_kwargs

# ============================================================
# CONFIGURACIÓN
# ============================================================
# Para departamentos en alquiler en Arequipa:
#   URL base: https://urbania.pe/buscar/alquiler-de-departamentos-en-arequipa--arequipa?page={n}
# Para departamentos en venta en Arequipa:
#   URL base: https://urbania.pe/buscar/venta-de-departamentos-en-arequipa--arequipa?page={n}
#
# CAMBIA esta URL según lo que quieras scrapear.
# ============================================================
BASE_PATTERN = "https://urbania.pe/buscar/venta-de-departamentos-en-arequipa--arequipa?page={}"
TOTAL_PAGINAS = 300  # Tope de seguridad, nunca prueba de fin del listado.
SITE_DOMAIN = "https://urbania.pe"
OUTPUT_FILE = f"urbania_arequipa_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

GUARDAR_CADA_N_PAGINAS = 2
detener = False


def construir_url_pagina(url_base, n):
    from scrapi.source_config import page_url
    return page_url('urbania', url_base, n)


def guardar_excel(todas):
    """Guarda la lista de propiedades en un archivo Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Propiedades Urbania'

    if todas:
        headers = list(todas[0].keys())
        ws.append(headers)
        for prop in todas:
            ws.append([prop.get(h, '') for h in headers])

        for col in ws.columns:
            max_len = max((len(str(cell.value or '')) for cell in col), default=0)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    wb.save(OUTPUT_FILE)
    con_coords = sum(1 for p in todas if p.get('Coordenadas'))
    print(f"\n[CHECKPOINT] Guardado -> {OUTPUT_FILE}")
    print(f"  Registros: {len(todas)} | Con coordenadas: {con_coords} | Sin coordenadas: {len(todas)-con_coords}")


def manejar_sigint(sig, frame):
    """Manejador de Ctrl+C: marca bandera para detener el loop."""
    global detener
    print("\n\n[!] Ctrl+C detectado! Terminando despues de la pagina actual...")
    detener = True


def decodificar_coordenadas(base64_str):
    """Decodifica las coordenadas en base64.
    Ej: 'LTE2LjM5MjE4NDM5NzE0NzUwMA==' -> '-16.392184397147500' -> -16.392184397147500
    """
    try:
        valor = base64.b64decode(base64_str).decode('utf-8')
        return float(valor)
    except Exception:
        return None


# Títulos de páginas de bloqueo/challenge que Urbania (Cloudflare u otros)
# puede presentar. El antiguo chequeo literal "Just a moment" ya no bastaba.
_TITULOS_BLOQUEO = (
    'just a moment',
    'attention required',
    'access denied',
    'checking your browser',
    'please verify you are a human',
    'verify you are human',
    'unusual traffic',
    'captcha',
    'forbidden',
    'demasiadas solicitudes',
    'unable to connect',
)


def _titulo_bloqueado(titulo):
    t = (titulo or '').strip().lower()
    if not t:
        return False
    return any(m in t for m in _TITULOS_BLOQUEO)


def _id_ficha_en_url(url):
    """Extrae el posting id numérico (token durable) de una URL de Urbania."""
    path = urlsplit(url).path.rstrip('/')
    nums = re.findall(r'\d{6,}', path)
    return nums[-1] if nums else None


def _misma_ficha_urbania(requested, current):
    """True si la URL actual sigue apuntando a la misma ficha solicitada.

    Tolera redirects canónicos (cambio de slug o prefijo www) porque el
    posting id numérico se conserva en la ruta final.
    """
    rp = urlsplit(requested).path.rstrip('/')
    cp = urlsplit(current).path.rstrip('/')
    if rp == cp:
        return True
    rid = _id_ficha_en_url(requested)
    return bool(rid and rid in cp)


async def _esperar_carga_real(page, timeout=30):
    """Espera un documento con título real (sin challenge ni página vacía).

    Returns: (listo, titulo). Un título vacío o de challenge se considera
    'todavía no listo'; solo un título real (contenido servido) cuenta.
    Siempre acotado por reloj (nunca excede ``timeout``), e imprime avances
    para que el proceso no parezca congelado.
    """
    print(f"      [espera] comprobando documento (hasta {timeout}s)...")
    inicio = asyncio.get_event_loop().time()
    ultimo_aviso = 0.0
    while True:
        transcurrido = asyncio.get_event_loop().time() - inicio
        if transcurrido >= timeout:
            break
        try:
            titulo = (await page.title() or '').strip()
        except Exception:
            titulo = ''
        if titulo and not _titulo_bloqueado(titulo):
            return True, titulo
        if transcurrido - ultimo_aviso >= 5:
            print(f"      [espera] título actual={titulo[:60]!r} ({int(transcurrido)}s/{int(timeout)}s)")
            ultimo_aviso = transcurrido
        await asyncio.sleep(1.5)
    return False, ''


async def esperar_cloudflare(page, timeout=20):
    """Espera a que Cloudflare resuelva el challenge (listado o ficha).

    ACOTADO a ~52 s como máximo (fase pasiva + 1 reload + fase corta) para
    NUNCA pasarse del presupuesto de 100 s que paged_engine.prepare_detail
    impone vía asyncio.wait_for. Si el challenge no se despeja, devuelve
    False y navegar_con_cloudflare arma un error visible con diagnóstico.
    """
    print("   Esperando resolucion de Cloudflare...")
    fase1 = min(int(timeout or 20), 20)
    ok, titulo = await _esperar_carga_real(page, fase1)
    if ok:
        print(f"   Cloudflare resuelto! Titulo: {titulo}")
        return True
    print("   [WARN] Challenge no resuelto pasivamente; recargando una vez...")
    try:
        await page.reload(wait_until='domcontentloaded', timeout=20000)
    except Exception as exc:
        print(f"   [WARN] Error en reload: {exc}")
    ok, titulo = await _esperar_carga_real(page, 12)
    if ok:
        print(f"   Cloudflare resuelto tras reload! Titulo: {titulo}")
        return True
    print("   [WARN] Timeout esperando Cloudflare")
    return False


async def navegar_con_cloudflare(page, url, timeout=20):
    """Navega a una URL esperando que Cloudflare se resuelva.

    No traga errores ni oculta el motivo del fallo: si el goto falla, si
    Cloudflare no se despeja o si la URL final ya no es la ficha solicitada,
    levanta un RuntimeError con diagnóstico (título, estado HTTP y URL final)
    para que paged_engine.prepare_detail reintente y el log muestre qué
    respondió Urbania realmente.
    """
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    except Exception as exc:
        print(f"   [WARN] Error en navegacion: {exc}")
        raise RuntimeError(f'navigation.failed: {exc}') from exc
    if not await esperar_cloudflare(page, timeout):
        try:
            titulo_obs = (await page.title() or '').strip()
        except Exception:
            titulo_obs = ''
        status = getattr(page, '_scraping_document_status', None)
        detalle = 'navigation.blocked: Urbania no confirmó acceso al contenido'
        partes = []
        if titulo_obs:
            partes.append(f'título={titulo_obs[:80]!r}')
        if status is not None:
            partes.append(f'HTTP {status}')
        try:
            final = page.url
            if final and 'about:' not in final:
                partes.append(final[:160])
        except Exception:
            pass
        if partes:
            detalle += ' (' + '; '.join(partes) + ')'
        print(f"   [BLOCKED] {detalle}")
        raise RuntimeError(detalle)
    # Verificar que seguimos en Urbania y en la misma ficha solicitada.
    try:
        from scrapi.source_config import validate_url
        validate_url('urbania', page.url)
    except ValueError as exc:
        raise RuntimeError(f'navigation.redirected: {exc}') from exc
    if not _misma_ficha_urbania(url, page.url):
        raise RuntimeError('navigation.redirected: Urbania redirigió fuera de la ficha solicitada')
    await page.wait_for_timeout(1500)
    return await page.title()


async def extraer_listado(page):
    """
    Extrae las propiedades de la página de listado actual.
    Las tarjetas tienen data-qa="posting PROPERTY" o data-qa="posting DEVELOPMENT".
    """
    props = []

    # Extraemos todas las tarjetas via evaluate para obtener sus atributos y texto
    data = await page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-qa^="posting"]');
            const results = [];
            for (const card of cards) {
                const qa = card.getAttribute('data-qa') || '';
                const id = card.getAttribute('data-id') || '';
                const urlRel = card.getAttribute('data-to-posting') || '';

                const priceEl = card.querySelector('[data-qa="POSTING_CARD_PRICE"]');
                const price = priceEl ? priceEl.textContent.trim() : '';

                const featuresEl = card.querySelector('[data-qa="POSTING_CARD_FEATURES"]');
                const features = featuresEl ? featuresEl.textContent.trim() : '';

                const locationEl = card.querySelector('[data-qa="POSTING_CARD_LOCATION"]');
                const location = locationEl ? locationEl.textContent.trim() : '';

                const descEl = card.querySelector('[data-qa="POSTING_CARD_DESCRIPTION"]');
                const description = descEl ? descEl.textContent.trim() : '';

                // Intentar extraer titulo del listado
                const titleEl = card.querySelector('h2, .postingCard-module__posting-description');
                const title = titleEl ? titleEl.textContent.trim() : '';

                // Extraer imagen
                const imgEl = card.querySelector('img[fetchpriority="high"]');
                const imgSrc = imgEl ? imgEl.getAttribute('src') || '' : '';

                const tipo = qa.includes('DEVELOPMENT') ? 'Proyecto' : 'Clasificado';

                results.push({
                    id: id,
                    tipo: tipo,
                    tipo_qa: qa,
                    url: urlRel,
                    precio: price,
                    caracteristicas: features,
                    ubicacion: location,
                    descripcion: description,
                    imagen: imgSrc,
                    titulo: title,
                });
            }
            return results;
        }
    """)

    for item in data:
        # Solo propiedades que tienen URL
        if not item['url']:
            continue

        href = item['url']
        if href.startswith('/'):
            href = SITE_DOMAIN + href

        # Parsear características: ej "220 m² tot.  3 dorm.  3 baños  2 estac."
        feats = item['caracteristicas']

        props.append({
            'ID':              item['id'],
            'Tipo Listado':    item['tipo'],
            'Precio':          item['precio'],
            'Caracteristicas': feats,
            'Ubicacion':       item['ubicacion'],
            'Descripcion':     item['descripcion'][:500] if item['descripcion'] else '',
            'URL Propiedad':   href,
            'Imagen URL':      item['imagen'],
            'Area Total':      '',
            'Dormitorios':     '',
            'Banos':           '',
            'Estacionamientos':'',
            'Latitud':         '',
            'Longitud':        '',
            'Coordenadas':     '',
            'Google Maps Link':'',
            'Titulo':          item.get('titulo', ''),
        })

    # El listado expone su estado en window.__PRELOADED_STATE__ con la
    # geolocalización de cada aviso (postingGeolocation.geolocation). Como el
    # listado NO está bloqueado por Cloudflare (a diferencia de las fichas),
    # esto captura coordenadas desde la página de búsqueda sin abrir cada ficha.
    try:
        geo_por_id = await page.evaluate("""() => {
            const out = {};
            try {
                const st = window.__PRELOADED_STATE__;
                const list = (st && st.listStore && st.listStore.listPostings) || [];
                for (const p of list) {
                    const g = p && p.postingGeolocation && p.postingGeolocation.geolocation;
                    if (g && g.latitude != null && g.longitude != null && p.postingId != null) {
                        const la = Number(g.latitude), lo = Number(g.longitude);
                        if (la > -18.5 && la < -0.1 && lo > -81.5 && lo < -68.5) {
                            out[String(p.postingId)] = [la, lo];
                        }
                    }
                }
            } catch (e) { /* el estado puede no existir en otras vistas */ }
            return out;
        }""")
    except Exception:
        geo_por_id = {}

    con_geo = 0
    if isinstance(geo_por_id, dict):
        for p in props:
            par = geo_por_id.get(str(p['ID']))
            if not par:
                # El data-id de la tarjeta no siempre coincide con el postingId
                # del estado; el id numérico al final de la URL de la ficha sí.
                m_id = re.search(r'(\d{6,})/?$', str(p.get('URL Propiedad') or ''))
                if m_id:
                    par = geo_por_id.get(m_id.group(1))
            if par:
                lat, lng = par[0], par[1]
                p['Latitud']          = lat
                p['Longitud']         = lng
                p['Coordenadas']      = f"{lat},{lng}"
                p['Google Maps Link'] = f"https://www.google.com/maps?q={lat},{lng}"
                con_geo += 1
        if con_geo:
            print(f"   [OK] {con_geo}/{len(props)} avisos con coordenadas desde el listado")

    # Enriquecido por HTTP de la ficha (PAUSADO): Urbania publica la geolocalización
    # en el listado solo para una parte de los avisos; el resto la tiene en su
    # ficha (mapLatOf/mapLngOf). Se consultan de a UNA, con pausa aleatoria de
    # ~2-4s y usando las cookies del navegador (cf_clearance) + Referer, para no
    # gatillar el bloqueo de Cloudflare por ráfaga. Si fallan varias seguidas se
    # detiene. Nunca hace fallar el scraping.
    global _http_fallos_seguidos
    faltantes = [p for p in props if not p.get('Coordenadas') and p.get('URL Propiedad')]
    if faltantes and _http_fallos_seguidos < 5:
        cookie_hdr = ''
        try:
            cookies = await page.context.cookies()
            cookie_hdr = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
        except Exception:
            cookie_hdr = ''
        try:
            referer = page.url
        except Exception:
            referer = ''
        for p in faltantes:
            if _http_fallos_seguidos >= 5:
                print("   [INFO] Varias fichas por HTTP fallaron; se detiene el enriquecido")
                break
            lat, lng = await _coord_ficha_http(p['URL Propiedad'], cookie_hdr, referer)
            if lat is not None:
                _aplicar_coords(p, lat, lng)
                _http_fallos_seguidos = 0
            else:
                _http_fallos_seguidos += 1
            await asyncio.sleep(random.uniform(2.0, 4.0))
        extra = sum(1 for p in faltantes if p.get('Coordenadas'))
        if extra:
            print(f"   [OK] {extra} coords adicionales vía ficha (pausado)")

    return props


_HTTP_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-PE,es;q=0.9,en;q=0.8',
}
_http_detalle_bloqueado = False
_http_fallos_seguidos = 0


def _fetch_html_sync(url, cookie_hdr='', referer=''):
    headers = dict(_HTTP_HEADERS)
    if cookie_hdr:
        headers['Cookie'] = cookie_hdr
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode('utf-8', errors='replace')


async def _coord_ficha_http(url, cookie_hdr='', referer=''):
    """Lee mapLatOf/mapLngOf de la ficha con HTTP simple (sin navegador)."""
    try:
        html = await asyncio.wait_for(
            asyncio.to_thread(_fetch_html_sync, url, cookie_hdr, referer), timeout=14)
    except Exception:
        return None, None
    return _coordenadas_desde_html(html)


def _aplicar_coords(prop, lat, lng):
    prop['Latitud']          = lat
    prop['Longitud']         = lng
    prop['Coordenadas']      = f"{lat},{lng}"
    prop['Google Maps Link'] = f"https://www.google.com/maps?q={lat},{lng}"


def _coordenadas_desde_html(html):
    """Extrae lat/lng de la ficha desde mapLatOf/mapLngOf (base64) del HTML.

    Urbania sirve las coordenadas en variables inline que pueden llevar o no
    prefijo const/let/var. Retorna (lat, lng) si decodifican a una ubicación
    válida dentro de Perú; si no, (None, None).
    """
    if not html:
        return None, None
    m_lat = re.search(r'(?:const|let|var)?\s*mapLatOf\s*=\s*["\']([^"\']+)["\']', html)
    m_lng = re.search(r'(?:const|let|var)?\s*mapLngOf\s*=\s*["\']([^"\']+)["\']', html)
    if not (m_lat and m_lng):
        return None, None
    lat = decodificar_coordenadas(m_lat.group(1))
    lng = decodificar_coordenadas(m_lng.group(1))
    if lat is None or lng is None:
        return None, None
    # Filtro de sanidad: coordenadas dentro de Perú
    if -18.5 < lat < -0.1 and -81.5 < lng < -68.5:
        return lat, lng
    return None, None


async def extraer_detalle(page, prop):
    """
    Navega a la ficha de detalle y extrae coordenadas + datos extra.
    Las coordenadas estan codificadas en base64 en variables JS:
        mapLatOf = "base64_string";
        mapLngOf = "base64_string";
    """
    url = prop['URL Propiedad']
    if not url:
        return

    # Navegación con detección de bloqueo y redirects. Los errores
    # navigation.* se propagan tal cual (sin re-empaquetarlos) para que
    # paged_engine.prepare_detail reintente con la pestaña ya navegada.
    await navegar_con_cloudflare(page, url, timeout=30)
    await page.wait_for_timeout(2000)

    try:
        # Las coordenadas están en variables inline de la ficha (mapLatOf/mapLngOf,
        # en base64). Se parsean en Python sobre el HTML renderizado para tolerar
        # los prefijos (const/let/var) y espacios que usa cada plantilla de Urbania.
        html_ficha = await page.content()
        lat, lng = _coordenadas_desde_html(html_ficha)
        if lat is not None and lng is not None:
            prop['Latitud']          = lat
            prop['Longitud']         = lng
            prop['Coordenadas']      = f"{lat},{lng}"
            prop['Google Maps Link'] = f"https://www.google.com/maps?q={lat},{lng}"
            print(f"   [OK] Coordenadas: {lat}, {lng}")
        else:
            print(f"   [WARN] Sin coordenadas en la pagina")

        # Extraer titulo y más detalles
        detalles = await page.evaluate("""
            () => {
                const result = {};

                // Titulo del proyecto/propiedad
                const h1 = document.querySelector('h1.title-h1-development, h1.title-property');
                if (h1) result.titulo = h1.textContent.trim();

                // Precio desde el DOM
                const priceEl = document.querySelector('.price-operation-type .list-prices');
                if (priceEl) result.precio_detalle = priceEl.textContent.replace(/\\s+/g, ' ').trim();

                // Ubicacion
                const locEl = document.querySelector('#ref-map, .section-location-property h4');
                if (locEl) result.ubicacion_detalle = locEl.textContent.trim();

                // Caracteristicas principales
                const features = [];
                document.querySelectorAll('.nf-container .item .label').forEach(el => {
                    features.push(el.textContent.trim());
                });
                result.caracteristicas = features.join(' | ');

                // Descripcion completa
                const descEl = document.querySelector('#longDescription');
                if (descEl) result.descripcion_completa = descEl.textContent.replace(/\\s+/g, ' ').trim();

                // Direccion
                const addrEl = document.querySelector('.section-location-property h4');
                if (addrEl) result.direccion = addrEl.textContent.trim();

                return result;
            }
        """)

        if detalles:
            if detalles.get('titulo'):
                prop['Titulo'] = detalles['titulo']
            if detalles.get('precio_detalle') and not prop['Precio']:
                prop['Precio'] = detalles['precio_detalle']
            if detalles.get('ubicacion_detalle'):
                prop['Ubicacion'] = detalles['ubicacion_detalle']
            if detalles.get('caracteristicas'):
                prop['Caracteristicas'] = detalles['caracteristicas']
            if detalles.get('descripcion_completa'):
                prop['Descripcion'] = detalles['descripcion_completa'][:800]

        # Parsear caracteristicas para extraer area, dormitorios, banos, estac.
        feats = prop.get('Caracteristicas', '')
        m_area = re.search(r'(?<![\d.,])(\d+(?:[.,]\d+)*)\s*m²\s*tot', feats)
        m_dorm = re.search(r'(\d+)\s*dorm', feats)
        m_bano = re.search(r'(\d+)\s*bañ', feats)
        m_estac = re.search(r'(\d+)\s*estac', feats)

        if m_area:    prop['Area Total']        = m_area.group(1) + ' m²'
        if m_dorm:   prop['Dormitorios']        = m_dorm.group(1)
        if m_bano:   prop['Banos']              = m_bano.group(1)
        if m_estac:  prop['Estacionamientos']   = m_estac.group(1)

    except Exception as e:
        print(f"   [ERROR] Error en detalle: {e}")
        raise RuntimeError(f'detail.extraction_failed: {e}') from e


async def main():
    from scrapi.standalone import export_portal
    await asyncio.to_thread(export_portal, 'urbania')


if __name__ == '__main__':
    asyncio.run(main())
