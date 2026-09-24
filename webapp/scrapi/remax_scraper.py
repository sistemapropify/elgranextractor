import asyncio
import re
import unicodedata
import openpyxl
import signal
import sys
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
from datetime import datetime
from camoufox.async_api import AsyncCamoufox
from scrapi.camoufox_launcher import camoufox_kwargs
from scrapi.remax_areas import calcular_areas_remax as calcular_areas
from urllib.request import Request, urlopen
from captura.azure_storage import upload_bytes

BASE_URL = "https://www.remax.pe/web/search/all/propertys/list/?departament__in=4&page={}"
SITE_DOMAIN = "https://www.remax.pe"
TOTAL_PAGES = 300  # Safety ceiling; the common engine verifies completion.
OUTPUT_FILE = f"remax_arequipa_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

# Control de guardado periodico
GUARDAR_CADA_N_PAGINAS = 3  # guarda Excel cada N paginas
detener = False  # bandera para Ctrl+C


# =========================================================================
# NORMALIZACION / ESTANDARIZACION
# Convierte el diccionario "crudo" de REMAX al esquema estandarizado
# compartido con Adondevivir, Properati y Urbania.
# =========================================================================

DISTRITOS_AREQUIPA_KNOWN = [
    "Arequipa", "Cayma", "Yanahuara", "Cerro Colorado", "Jose Luis Bustamante Y Rivero",
    "Paucarpata", "Sachaca", "Characato", "Sabandia", "Socabaya", "Miraflores",
    "Mariano Melgar", "Alto Selva Alegre", "Hunter", "Tiabaya", "Uchumayo",
    "La Joya", "Yura", "Cerro Colorado", "Mollendo", "Mejia", "Camana", "Islay",
]


def _sin_acentos(s: str) -> str:
    """Quita tildes/diacriticos para comparar textos sin importar acentuacion."""
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    ).lower()


def limpiar_precio(texto):
    """
    'S/. 1'372,950.00'  -> 1372950.0
    'USD 405,000.00'    -> 405000.0
    ''                  -> None
    Quita simbolos de moneda, comillas (separador de miles en formato peruano
    tipo 1'372,950) y comas (separador de miles), deja el punto como decimal.
    """
    if not texto:
        return None
    texto = re.sub(r'^(?:S/\.?|USD|US\$|PEN|\$)\s*', '', str(texto).strip(), flags=re.I)
    solo_numeros = re.sub(r"[^\d.,]", "", str(texto))
    solo_numeros = solo_numeros.replace(",", "")
    if not solo_numeros:
        return None
    try:
        return float(solo_numeros)
    except ValueError:
        return None


def parse_num_prefix(texto):
    """'1 Paralelo Techado' -> 1 ; '' -> None"""
    if not texto:
        return None
    m = re.match(r"\s*(\d+)", str(texto))
    return int(m.group(1)) if m else None


def area_desde_medidas(medidas):
    """'8.00 X 16.00' -> 128.0 ; '0.00 X 0.00' o vacio -> None"""
    if not medidas:
        return None
    m = re.match(r"\s*([\d.]+)\s*[xX]\s*([\d.]+)", str(medidas))
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if a > 0 and b > 0:
            return round(a * b, 2)
    return None


def area_desde_texto(texto):
    """'128 m2' / '128.5' -> 128.0 / 128.5 ; vacio -> None"""
    if not texto:
        return None
    m = re.search(r"([\d,.]+)", str(texto))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def calcular_area_m2(prop):
    """Prioridad: Area Construida > Area Terreno > Medidas (frente x fondo) > Descripcion."""
    campos = ("Area Terreno", "Area Ocupada", "Area Construida") if 'TERRENO' in str(prop.get('Tipo', '')).upper() else ("Area Construida", "Area Ocupada", "Area Terreno")
    for campo in campos:
        val = area_desde_texto(prop.get(campo))
        if val:
            return val
    val = area_desde_medidas(prop.get("Medidas"))
    if val:
        return val
    desc = prop.get("Descripcion", "") or ""
    m = re.search(r"([\d]+(?:[.,]\d+)?)\s*m(?:2|\u00b2)", desc)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def clasificar_tipo_inmueble(tipo_raw):
    """'DEPARTAMENTO FLAT EN VENTA' -> 'Departamento'"""
    t = (tipo_raw or "").upper()
    if "DEPARTAMENTO" in t:
        return "Departamento"
    if "CASA" in t:
        return "Casa"
    if "TERRENO" in t:
        return "Terreno"
    if "OFICINA" in t:
        return "Oficina"
    if "LOCAL" in t or "ALMACEN" in t or "ALMAC\u00c9N" in t:
        return "Local"
    if "HOTEL" in t:
        return "Hotel"
    return "Otro"


def clasificar_operacion(tipo_raw):
    """'DEPARTAMENTO FLAT EN VENTA' -> 'Venta' ; '... EN ALQUILER' -> 'Alquiler'"""
    t = (tipo_raw or "").upper()
    if "ALQUILER" in t:
        return "Alquiler"
    if "VENTA" in t:
        return "Venta"
    return None


def normalizar_conteo(valor, tipo_inmueble, permite_cero_en=("Terreno",)):
    """
    REMAX usa 0 tanto para 'sin dato' como para 'terreno sin habitaciones'.
    Si es 0 y el inmueble NO es un tipo donde 0 es un valor real -> None (sin dato).
    """
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        return None
    if n == 0 and tipo_inmueble not in permite_cero_en:
        return None
    return n


def normalizar_ubicacion(texto):
    if not texto:
        return None
    return texto.strip().title()


def normalizar_distrito(prop):
    """REMAX orders its location as departamento, provincia, distrito.

    Normalize again at the output boundary so resumed/older raw candidates
    cannot persist the whole location in the district column.
    """
    parts = [part.strip() for part in (prop.get('Distrito') or '').split(',') if part.strip()]
    if parts:
        return normalizar_ubicacion(parts[-1])
    location = [part.strip() for part in (prop.get('Ubicacion Full') or '').split(',') if part.strip()]
    # A shorter general location is not evidence of a district.
    return normalizar_ubicacion(location[-1]) if len(location) >= 3 else None


def parsear_antiguedad(texto):
    if not texto:
        return None
    m = re.search(r"(\d+)", str(texto))
    return int(m.group(1)) if m else None


def construir_amenities(prop):
    """Junta los servicios/atributos sueltos de REMAX en una sola lista 'Label: valor | ...'."""
    piezas = []
    mapa = {
        "Serv. Agua": "Agua",
        "Energia Electrica": "Electricidad",
        "Serv. Drenaje": "Desague",
        "Serv. Gas": "Gas",
    }
    for campo_original, etiqueta in mapa.items():
        valor = (prop.get(campo_original) or "").strip()
        if valor and valor.lower() not in ("no tiene", "-", ""):
            piezas.append(f"{etiqueta}: {valor}")
    cocheras_txt = (prop.get("Cocheras") or "").strip()
    # 'Cocheras' trae "1 Paralelo Techado": la parte no numerica es info de amenity
    resto_cochera = re.sub(r"^\s*\d+\s*", "", cocheras_txt).strip()
    if resto_cochera and (parse_num_prefix(cocheras_txt) or 0) > 0:
        piezas.append(f"Cochera: {resto_cochera}")
    pisos = prop.get("Pisos")
    if pisos not in (None, "", 0, "0"):
        piezas.append(f"Pisos: {pisos}")
    return " | ".join(piezas)


def construir_agencia_agente(prop):
    oficina = (prop.get("Oficina") or "").strip()
    agente = (prop.get("Agente") or "").strip()
    if oficina and agente:
        return f"{oficina} - {agente}"
    return oficina or agente or None


def construir_titulo(tipo_inmueble, operacion, distrito):
    """REMAX no trae titulo propio: se sintetiza uno a partir del tipo/operacion/distrito."""
    partes = [p for p in (tipo_inmueble, f"en {operacion}" if operacion else None,
                           f"- {distrito}" if distrito else None) if p]
    return " ".join(partes) if partes else None


def estandarizar(prop, fecha_extraccion):
    """Convierte un registro crudo de REMAX al esquema estandarizado comun."""
    tipo_raw = prop.get("Tipo", "")
    tipo_inmueble = clasificar_tipo_inmueble(tipo_raw)
    operacion = clasificar_operacion(tipo_raw)
    distrito = normalizar_distrito(prop)
    provincia = normalizar_ubicacion(prop.get("Provincia"))
    try:
        lat, lng = float(prop.get('Latitud')), float(prop.get('Longitud'))
        if not (-18.5 < lat < -0.1 and -81.5 < lng < -68.5):
            lat = lng = None
    except (ValueError, TypeError):
        lat = lng = None

    return {
        "fuente": "REMAX",
        "id_origen": str(prop.get("ID", "")).strip(),
        "fecha_extraccion": fecha_extraccion,
        "titulo": construir_titulo(tipo_inmueble, operacion, distrito),
        "tipo_inmueble": tipo_inmueble,
        "tipo_operacion": operacion,
        "precio_soles": limpiar_precio(prop.get("Precio S/.")),
        "precio_usd": limpiar_precio(prop.get("Precio USD")),
        # Área principal + las dos superficies por separado (terreno / construida).
        **calcular_areas(prop),
        "dormitorios": normalizar_conteo(prop.get("Habitaciones"), tipo_inmueble),
        "banos": normalizar_conteo(prop.get("Banos"), tipo_inmueble),
        "estacionamientos": parse_num_prefix(prop.get("Cocheras")),
        "distrito": distrito,
        "departamento": normalizar_ubicacion(prop.get('Departamento')),
        "provincia": provincia,
        # The dashboard's Dirección column should contain the district for
        # REMAX. Keep the original hierarchy in datos_crudos['Ubicacion Full'].
        "direccion_texto": distrito,
        "descripcion": (prop.get("Descripcion") or "").strip() or None,
        "amenities": construir_amenities(prop) or None,
        "latitud": lat,
        "longitud": lng,
        "precision_ubicacion": 'exacta' if lat is not None else 'desconocida',
        "url": prop.get("URL Propiedad") or None,
        "imagen_url": prop.get("Imagen URL") or None,
        "antiguedad_anios": parsear_antiguedad(prop.get("Antiguedad")),
        "agencia_agente": construir_agencia_agente(prop),
    }


CAMPOS_ESTANDAR = [
    "fuente", "id_origen", "fecha_extraccion", "titulo", "tipo_inmueble",
    "tipo_operacion", "precio_soles", "precio_usd", "area_m2",
    "area_terreno", "area_construida", "dormitorios",
    "banos", "estacionamientos", "distrito", "provincia", "direccion_texto",
    "descripcion", "amenities", "latitud", "longitud", "url", "imagen_url",
    "antiguedad_anios", "agencia_agente", "departamento", "precision_ubicacion",
]


def guardar_excel(todas):
    """Guarda dos hojas: 'Estandarizado' (esquema comun) y 'RAW_Original' (crudo, para QA)."""
    wb = openpyxl.Workbook()
    fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Hoja 1: Estandarizado ---
    ws_std = wb.active
    ws_std.title = "Estandarizado"
    ws_std.append(CAMPOS_ESTANDAR)
    for prop in todas:
        row = estandarizar(prop, fecha_extraccion)
        ws_std.append([row.get(c, "") for c in CAMPOS_ESTANDAR])
    for col in ws_std.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws_std.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    # --- Hoja 2: RAW_Original (crudo, tal como venia el script original) ---
    ws_raw = wb.create_sheet("RAW_Original")
    if todas:
        headers = list(todas[0].keys())
        ws_raw.append(headers)
        for prop in todas:
            ws_raw.append([prop.get(h, "") for h in headers])
        for col in ws_raw.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=0)
            ws_raw.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    wb.save(OUTPUT_FILE)
    con_coords = sum(1 for p in todas if p.get("Coordenadas"))
    con_banos = sum(1 for p in todas if normalizar_conteo(
        p.get("Banos"), clasificar_tipo_inmueble(p.get("Tipo", ""))) is not None)
    print(f"\n[CHECKPOINT] Guardado -> {OUTPUT_FILE}")
    print(f"  Registros: {len(todas)} | Con coordenadas: {con_coords} | "
          f"Sin coordenadas: {len(todas)-con_coords} | Con banos detectados: {con_banos}")


def manejar_sigint(sig, frame):
    """Manejador de Ctrl+C: marca bandera para detener el loop."""
    global detener
    print("\n\n[!] Ctrl+C detectado! Terminando despues de la pagina actual...")
    detener = True


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
    # Intento final
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
    if not await esperar_cloudflare(page, timeout):
        raise RuntimeError('navigation.blocked: Remax no confirmó acceso al contenido')
    await page.wait_for_timeout(1000)
    return await page.title()


def subir_imagen_a_blob(imagen_url, prop):
    """Copia la foto de Remax a nuestro contenedor ``propiedadesimagenes``.

    Remax publica las imágenes en un bucket privado (DigitalOcean Spaces) con
    una firma temporal: si solo se guarda la URL, al expirar la firma la ficha
    queda con 403 y el mapa no puede mostrarla. Por eso se copia a nuestro Blob
    durante el scraping, igual que Properati y Adondevivir.
    """
    if not imagen_url:
        return None

    try:
        req = Request(imagen_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
            'Referer': SITE_DOMAIN + '/',
        })
        with urlopen(req, timeout=25) as resp:
            content_type = resp.headers.get_content_type() or 'image/jpeg'
            content = resp.read()

        if not content:
            return None

        ext = 'jpg'
        lowered = (content_type or '').lower()
        if 'png' in lowered:
            ext = 'png'
        elif 'webp' in lowered:
            ext = 'webp'
        elif 'gif' in lowered:
            ext = 'gif'
        elif 'jpeg' in lowered or 'jpg' in lowered:
            ext = 'jpg'

        prop_id = str(prop.get('ID') or 'sin_id').strip()
        safe_id = re.sub(r'[^A-Za-z0-9_-]+', '_', prop_id)[:60]
        blob_name = f"propiedades/{safe_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        return upload_bytes(
            content,
            blob_name=blob_name,
            container_name='propiedadesimagenes',
            content_type=content_type,
            metadata={
                'fuente': 'remax',
                'id_origen': prop_id,
                'imagen_origen': imagen_url,
            },
        )
    except Exception as e:
        print(f"   [WARN] No se pudo subir imagen de Remax a Blob: {e}")
        return None


async def extraer_listado(page):
    """Read one DOM snapshot instead of thousands of remote element operations."""
    html = await page.content()
    return await asyncio.to_thread(parsear_listado_html, html)


def parsear_listado_html(html):
    """Parse the rendered grid/list using the same selectors and field mapping."""
    props = []
    cards = BeautifulSoup(html, 'html.parser').select('.__propiedadgen, .__propiedadgen2')

    for card in cards:
        try:
            id_el    = card.select_one('.badge-danger-xs')
            link_el  = card.select_one('.__imagen a')
            img_el   = card.select_one('.__imagen img')
            tipo_el  = card.select_one('.badge-blue-xs')
            wa_el    = card.select_one('.__agenteproint a[href*="wa.me"]')
            precio_els = card.select('.__casventap li')
            ubic_els   = card.select('.__casadat h5')

            precios = []
            for p in precio_els:
                t = p.get_text(' ', strip=True)
                if t != '-':
                    precios.append(t)

            feats = {}
            feat_els = card.select('.__icofeat')
            for f in feat_els:
                p_el = f.select_one('p')
                if p_el:
                    txt = p_el.get_text(' ', strip=True)
                    m = re.match(r'(.+?)\s*:\s*(.+)', txt)
                    if m:
                        feats[_sin_acentos(m.group(1).strip())] = m.group(2).strip()

            def feature(name):
                return feats.get(_sin_acentos(name), '')

            agency_lines = ubic_els[1].get_text('\n', strip=True).splitlines() if len(ubic_els) > 1 else []
            agency_lines = [line.strip() for line in agency_lines if line.strip()]

            wa_href  = wa_el.get('href', '') if wa_el else ''
            tel_m    = re.search(r'wa\.me\/(\d+)', wa_href) if wa_href else None
            ubic_raw = ubic_els[0].get_text(' ', strip=True) if ubic_els else ''
            ubic     = re.sub(r'\s+', ' ', ubic_raw).strip()
            parts    = [s.strip() for s in ubic.split(',') if s.strip()]

            # Convertir URL relativa a absoluta
            href_raw = link_el.get('href', '') if link_el else ''
            if href_raw and href_raw.startswith('/'):
                href_raw = SITE_DOMAIN + href_raw

            img_src = img_el.get('src', '') if img_el else ''
            if img_src and img_src.startswith('/'):
                img_src = SITE_DOMAIN + img_src

            props.append({
                'ID':               id_el.get_text(' ', strip=True) if id_el else '',
                'Tipo':             tipo_el.get_text(' ', strip=True) if tipo_el else '',
                'Precio S/.':       next((v for v in precios if re.match(r'^(S/|PEN)', v, re.I)), ''),
                'Precio USD':       next((v for v in precios if re.match(r'^(USD|US\$|\$)', v, re.I)), ''),
                'Departamento':     parts[0] if len(parts) > 0 else '',
                'Provincia':        parts[1] if len(parts) > 1 else '',
                'Distrito':         parts[-1] if len(parts) > 2 else '',
                'Ubicacion Full':   ubic,
                'Oficina':          agency_lines[0] if len(agency_lines) > 1 else '',
                'Agente':           ' '.join(agency_lines[1:]) if len(agency_lines) > 1 else '',
                'Telefono':         tel_m.group(1) if tel_m else '',
                'Area Terreno':     feature('Area Terreno'),
                'Area Construida':  feature('Area Construida'),
                'Area Ocupada':     feature('Area Ocupada'),
                'Pisos':            feature('Pisos'),
                'Habitaciones':     feature('Habitaciones'),
                'Banos':            feature('Banos'),
                'Cocheras':         feature('Cocheras'),
                'Medidas':          '',
                'Antiguedad':       '',
                'Medios Banos':     '',
                'Serv. Agua':       '',
                'Energia Electrica':'',
                'Serv. Drenaje':    '',
                'Serv. Gas':        '',
                'Descripcion':      '',
                'Fecha Publicacion':'',
                'Latitud':          '',
                'Longitud':         '',
                'Coordenadas':      '',
                'Google Maps Link': '',
                'URL Propiedad':    href_raw,
                'Imagen URL':       img_src,
                'WhatsApp Link':    wa_href,
            })
        except Exception as e:
            # A silently skipped card must never certify complete coverage.
            raise RuntimeError(f'listing.card_failed: {e}') from e

    return props


def coordenadas_marcador(scripts):
    """Only accept the marker attached to the property's map, never its viewport."""
    for script in scripts:
        maps = re.findall(r'(?:var|let|const)\s+(\w+)\s*=\s*L\.map\(\s*[\'"]map_property[\'"]', script)
        for map_name in maps:
            pattern = (r'L\.marker\(\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*'
                       r'(-?\d+(?:\.\d+)?)\s*\][^;]*?\.addTo\(\s*'
                       + re.escape(map_name) + r'\s*\)')
            pairs = {(float(a), float(b)) for a, b in re.findall(pattern, script)}
            if len(pairs) == 1:
                lat, lng = pairs.pop()
                if -18.5 < lat < -0.1 and -81.5 < lng < -68.5:
                    return {'lat': lat, 'lng': lng}
    return None


async def extraer_detalle(page, prop):
    """Navega a la ficha de detalle y extrae coordenadas + campos extras."""
    url = prop['URL Propiedad']
    if not url:
        return

    try:
        await navegar_con_cloudflare(page, url, timeout=30)
        # Esperar a que Leaflet inicialice el mapa
        await page.wait_for_timeout(2000)

        prop['Latitud'] = prop['Longitud'] = None
        prop['Coordenadas'] = ''
        scripts = await page.evaluate("() => Array.from(document.querySelectorAll('script'), s => s.textContent)")
        coords = coordenadas_marcador(scripts)
        if not coords:
            raise RuntimeError('location.marker_missing: no se pudo verificar el marcador de map_property')
        prop['_location_evidence'] = {'source': 'map_property.marker', 'precision': 'exacta', 'url': url}
        logger.info('remax.location.extracted id=%s precision=exacta source=map_property.marker', prop.get('ID'))

        if coords and coords.get('lat'):
            lat, lng = coords['lat'], coords['lng']
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
            prop['Google Maps Link'] = f"https://www.google.com/maps/search/?api=1&query={prop['Ubicacion Full'].replace(' ', '+')}"
            print(f"   [WARN] Sin coordenadas en la pagina")

        # Campos de detalle
        campos = await page.evaluate("""
            () => {
                const result = {};
                document.querySelectorAll('.__bodyt').forEach(label => {
                    const key = label.textContent.replace(/\\s+/g, ' ').trim();
                    const val = label.nextElementSibling;
                    if (val && val.classList.contains('__bodyc'))
                        result[key] = val.textContent.trim();
                });
                return result;
            }
        """)

        def get(k):
            # BUGFIX: la comparacion original 'k.lower() in fk.lower()' nunca
            # matcheaba 'Banos' contra la etiqueta real 'Baños' por la enie
            # (banos no es substring de baños). Se compara sin acentos.
            k_norm = _sin_acentos(k)
            for fk, fv in campos.items():
                if k_norm == _sin_acentos(fk).strip().rstrip(':'):
                    return fv
            for fk, fv in campos.items():
                if k_norm == 'banos' and ('1/2' in fk or 'medio' in _sin_acentos(fk)):
                    continue
                if k_norm in _sin_acentos(fk):
                    return fv
            return ''

        if get('Area Terreno'):    prop['Area Terreno']      = get('Area Terreno')
        if get('Area Construida'): prop['Area Construida']   = get('Area Construida')
        if get('Medidas'):         prop['Medidas']            = get('Medidas')
        if get('Antiguedad'):      prop['Antiguedad']         = get('Antiguedad')
        if get('Pisos') or get('Piso'):
            prop['Pisos'] = get('Pisos') or get('Piso')
        if get('Habitaciones'):    prop['Habitaciones']      = get('Habitaciones')
        if get('Banos'):           prop['Banos']             = get('Banos')
        if get('1/2') or get('Medio'):
            prop['Medios Banos'] = get('1/2') or get('Medio')
        if get('Cocheras'):        prop['Cocheras']          = get('Cocheras')
        if get('Agua'):            prop['Serv. Agua']        = get('Agua')
        if get('Electrica') or get('Energia'):
            prop['Energia Electrica'] = get('Electrica') or get('Energia')
        if get('Drenaje'):         prop['Serv. Drenaje']     = get('Drenaje')
        if get('Gas'):             prop['Serv. Gas']         = get('Gas')
        if get('Area Libre'):      prop['Area Libre'] = get('Area Libre')
        if get('Area Ocupada'):    prop['Area Ocupada'] = get('Area Ocupada')

        # Descripcion
        desc_el = await page.query_selector('.__text_match')
        if desc_el:
            prop['Descripcion'] = (await desc_el.inner_text()).replace('\n', ' ').strip()

        # Fecha de publicacion
        fecha_el = await page.query_selector('.titulo_02')
        if fecha_el:
            texto_fecha = (await fecha_el.inner_text()).strip()
            if 'Publicado' in texto_fecha or 'publicado' in texto_fecha:
                prop['Fecha Publicacion'] = texto_fecha.replace('Publicado el :', '').replace('Publicado el:', '').strip()

        # Agente y oficina
        agent = await page.query_selector('.__datos h2')
        office = await page.query_selector('.__datos h4')
        if agent:
            prop['Agente'] = (await agent.inner_text()).strip()
        if office:
            prop['Oficina'] = (await office.inner_text()).strip()
        agente_els = await page.query_selector_all('.__casadat h5')
        if not prop.get('Agente') and len(agente_els) > 1:
            children = await page.evaluate("""
                (el) => {
                    const nodes = el.childNodes;
                    let oficina = '', agente = '';
                    for (const n of nodes) {
                        if (n.nodeType === 3 && n.textContent.trim()) {
                            oficina = n.textContent.trim();
                            break;
                        }
                    }
                    for (const n of nodes) {
                        if (n.nodeType === 1 && n.textContent.trim()) {
                            agente = n.textContent.trim();
                            break;
                        }
                    }
                    return { oficina, agente };
                }
            """, agente_els[1])
            prop['Oficina'] = children.get('oficina', '')
            prop['Agente']  = children.get('agente', '')

    except Exception as e:
        print(f"   [ERROR] Error en detalle: {e}")
        raise RuntimeError(f'detail.extraction_failed: {e}') from e
        prop['Google Maps Link'] = f"https://www.google.com/maps/search/?api=1&query={prop['Ubicacion Full'].replace(' ', '+')}"


async def main():
    from scrapi.standalone import export_portal
    await asyncio.to_thread(export_portal, 'remax')


if __name__ == '__main__':
    asyncio.run(main())
