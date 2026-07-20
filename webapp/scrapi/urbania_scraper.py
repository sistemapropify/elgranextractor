import asyncio
import re
import base64
import openpyxl
import signal
import sys
import json
from datetime import datetime
from camoufox.async_api import AsyncCamoufox

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
TOTAL_PAGINAS = 5  # Ajusta según el número de páginas (la página muestra 5)
SITE_DOMAIN = "https://urbania.pe"
OUTPUT_FILE = f"urbania_arequipa_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

GUARDAR_CADA_N_PAGINAS = 2
detener = False


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


async def esperar_cloudflare(page, timeout=30):
    """Espera a que Cloudflare resuelva el challenge."""
    print("   Esperando resolucion de Cloudflare...")
    inicio = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - inicio < timeout:
        try:
            titulo = await page.title()
            if "Just a moment" not in titulo and titulo.strip():
                print(f"   Cloudflare resuelto! Titulo: {titulo}")
                return True
        except Exception:
            pass
        await asyncio.sleep(2)
    await page.wait_for_timeout(5000)
    try:
        titulo = await page.title()
        if "Just a moment" not in titulo and titulo.strip():
            print(f"   Cloudflare resuelto! Titulo: {titulo}")
            return True
    except Exception:
        pass
    print("   [WARN] Timeout esperando Cloudflare")
    return False


async def navegar_con_cloudflare(page, url, timeout=30):
    """Navega a una URL esperando que Cloudflare se resuelva."""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    except Exception as e:
        print(f"   [WARN] Error en navegacion: {e}")
    await esperar_cloudflare(page, timeout)
    await page.wait_for_timeout(2000)
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
            'Titulo':          '',
        })

    return props


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

    try:
        await navegar_con_cloudflare(page, url, timeout=30)
        await page.wait_for_timeout(2000)

        # Extraer coordenadas via evaluate - buscar las variables JS
        coords_data = await page.evaluate("""
            () => {
                // Buscar en el HTML las variables mapLatOf y mapLngOf
                const html = document.documentElement.innerHTML;
                const latMatch = html.match(/const\\s+mapLatOf\\s*=\\s*["']([^"']+)["']/);
                const lngMatch = html.match(/const\\s+mapLngOf\\s*=\\s*["']([^"']+)["']/);
                return {
                    latB64: latMatch ? latMatch[1] : null,
                    lngB64: lngMatch ? lngMatch[1] : null
                };
            }
        """)

        if coords_data and coords_data.get('latB64') and coords_data.get('lngB64'):
            lat = decodificar_coordenadas(coords_data['latB64'])
            lng = decodificar_coordenadas(coords_data['lngB64'])
            if lat and lng:
                # Filtro de sanidad: coordenadas de Peru
                if -18.5 < lat < -0.1 and -81.5 < lng < -68.5:
                    prop['Latitud']          = lat
                    prop['Longitud']         = lng
                    prop['Coordenadas']      = f"{lat},{lng}"
                    prop['Google Maps Link'] = f"https://www.google.com/maps?q={lat},{lng}"
                    print(f"   [OK] Coordenadas: {lat}, {lng}")
                else:
                    print(f"   [WARN] Coords fuera de Peru: {lat},{lng}")
            else:
                print(f"   [WARN] No se pudieron decodificar coordenadas")
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
        m_area = re.search(r'(\d+)\s*m²\s*tot', feats)
        m_dorm = re.search(r'(\d+)\s*dorm', feats)
        m_bano = re.search(r'(\d+)\s*bañ', feats)
        m_estac = re.search(r'(\d+)\s*estac', feats)

        if m_area:    prop['Area Total']        = m_area.group(1) + ' m²'
        if m_dorm:   prop['Dormitorios']        = m_dorm.group(1)
        if m_bano:   prop['Banos']              = m_bano.group(1)
        if m_estac:  prop['Estacionamientos']   = m_estac.group(1)

    except Exception as e:
        print(f"   [ERROR] Error en detalle: {e}")


async def main():
    global detener
    todas = []

    # Registrar manejador de Ctrl+C
    signal.signal(signal.SIGINT, manejar_sigint)

    async with AsyncCamoufox(
        headless=False,
        os='windows',
        humanize=True,
        persistent_context=True,
        user_data_dir='./camoufox_session_urbania',
    ) as browser:

        page = await browser.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})

        # FASE 1: Extraer todas las paginas del listado
        print("=" * 60)
        print("FASE 1: Scrapeando paginas de listado")
        print(f"Total paginas: {TOTAL_PAGINAS} | Guardando Excel cada {GUARDAR_CADA_N_PAGINAS} paginas")
        print("Presiona Ctrl+C para guardar y salir")
        print("=" * 60)

        for n in range(1, TOTAL_PAGINAS + 1):
            if detener:
                print(f"\n[!] Deteniendo por solicitud del usuario...")
                break

            url = BASE_PATTERN.format(n)
            print(f"\n[Pagina {n}/{TOTAL_PAGINAS}]: {url}")
            try:
                titulo = await navegar_con_cloudflare(page, url)
                print(f"   Titulo: {titulo}")

                props = await extraer_listado(page)
                todas.extend(props)
                print(f"   -> {len(props)} propiedades extraidas (total: {len(todas)})")

                # Guardado periodico cada N paginas
                if n % GUARDAR_CADA_N_PAGINAS == 0 and todas:
                    guardar_excel(todas)

            except Exception as e:
                print(f"   [ERROR] en pagina {n}: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n[OK] FASE 1 completa: {len(todas)} propiedades encontradas")

        if not detener and todas:
            # FASE 2: Visitar cada ficha de detalle
            print("\n" + "=" * 60)
            print("FASE 2: Extrayendo coordenadas y detalles")
            print("=" * 60)

            for i, prop in enumerate(todas):
                if detener:
                    print(f"\n[!] Deteniendo por solicitud del usuario...")
                    break

                prop_id = prop.get('ID', '')
                ubic = prop.get('Ubicacion', '')
                print(f"\n[{i+1}/{len(todas)}] ID: {prop_id} - {ubic}")
                await extraer_detalle(page, prop)
                await asyncio.sleep(0.5)

        await page.close()

    # FASE 3: Exportar a Excel (siempre guarda al final)
    print("\n" + "=" * 60)
    print("FASE 3: Exportando Excel")
    print("=" * 60)

    guardar_excel(todas)
    con_coords = sum(1 for p in todas if p.get('Coordenadas'))
    print(f"\n[OK] DESCARGADO -> {OUTPUT_FILE}")
    print(f"Total: {len(todas)} | Con coordenadas: {con_coords} | Sin coordenadas: {len(todas)-con_coords}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupcion por teclado. El Excel se guardo con el progreso actual.")
        sys.exit(0)
