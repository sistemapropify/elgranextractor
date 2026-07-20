import asyncio
import re
import json
import openpyxl
import signal
import sys
import unicodedata
from datetime import datetime
from camoufox.async_api import AsyncCamoufox

# ============================================================
# CONFIGURACIÓN
# ============================================================
BASE_URL = "https://www.properati.com.pe/s/arequipa"  # Pagina 1
TOTAL_PAGINAS = 30  # Properati muestra ~30 paginas para Arequipa
SITE_DOMAIN = "https://www.properati.com.pe"
OUTPUT_FILE = f"properati_arequipa_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

GUARDAR_CADA_N_PAGINAS = 3
detener = False


# =========================================================================
# NORMALIZACION / ESTANDARIZACION (compartido con REMAX, Adondevivir, Urbania)
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
    'S/.306'            -> 306.0
    ''                  -> None
    Primero remueve prefijos de moneda conocidos (S/., S/, US$, USD, $)
    para evitar que el simbolo '/' o '.' residual produzca fracciones
    como 0.306 en vez de 306.
    """
    if not texto:
        return None
    s = str(texto).strip()
    # Remover prefijos de moneda conocidos al inicio de la cadena
    s = re.sub(r'^(?:S/\.?\s*|S/\s*|US[$]\s*|USD\s*|\$\s*)', '', s)
    # Si aun quedan simbolos de moneda no esperados, limpiarlos
    solo_numeros = re.sub(r"[^\d.,]", "", s)
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
    """
    '128 m2' / '128.5' -> 128.0 / 128.5 ; vacio -> None.
    Maneja formato peruano/espanol con punto como separador de miles:
    '5.795 m2' -> 5795.0   (periodo seguido de 3 digitos = miles)
    '1.234,56' -> 1234.56  (formato espanol mixto)
    """
    if not texto:
        return None
    m = re.search(r"([\d,.]+)", str(texto))
    if not m:
        return None
    s = m.group(1)
    # Detectar si el punto es separador de miles: '.XXX' (3 digitos despues del punto)
    # y no hay coma decimal -> tratar como miles
    if '.' in s and ',' not in s:
        # Si el patron es como 5.795 (punto cada 3 digitos)
        parts = s.split('.')
        if len(parts) >= 2 and all(len(p) == 3 for p in parts[1:]):
            # Es formato espanol: punto = separador de miles
            s = s.replace('.', '')
    elif ',' in s and '.' in s:
        # Formato mixto: 1.234,56 -> punto = miles, coma = decimal
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s and '.' not in s:
        # Coma como separador de miles (formato ingles) o decimal
        # Si el ultimo grupo tiene 3 digitos -> separador de miles: 5,795
        # Si tiene 1-2 digitos -> coma decimal: 1234,56
        parts = s.split(',')
        if len(parts) >= 2 and len(parts[-1]) == 3:
            # Parece formato de miles: 5,795  /  1,234,567
            s = s.replace(',', '')
        else:
            # Asumir coma decimal: 1234,56
            s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def calcular_area_m2(prop):
    """Prioridad: Area Construida > Area Terreno > Medidas (frente x fondo) > Descripcion."""
    for campo in ("Area Construida", "Area Terreno"):
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


def parsear_antiguedad(texto):
    if not texto:
        return None
    m = re.search(r"(\d+)", str(texto))
    return int(m.group(1)) if m else None


def construir_amenities(prop):
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
    resto_cochera = re.sub(r"^\s*\d+\s*", "", cocheras_txt).strip()
    if resto_cochera:
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
    partes = [p for p in (tipo_inmueble, f"en {operacion}" if operacion else None,
                           f"- {distrito}" if distrito else None) if p]
    return " ".join(partes) if partes else None


def estandarizar(prop, fecha_extraccion, fuente="Properati"):
    """Convierte un registro crudo al esquema estandarizado comun."""
    tipo_raw = prop.get("Tipo", "")
    tipo_inmueble = clasificar_tipo_inmueble(tipo_raw)
    operacion = clasificar_operacion(tipo_raw)
    distrito = normalizar_ubicacion(prop.get("Distrito"))
    provincia = normalizar_ubicacion(prop.get("Provincia"))

    return {
        "fuente": fuente,
        "id_origen": str(prop.get("ID", "")).strip(),
        "fecha_extraccion": fecha_extraccion,
        "titulo": construir_titulo(tipo_inmueble, operacion, distrito),
        "tipo_inmueble": tipo_inmueble,
        "tipo_operacion": operacion,
        "precio_soles": limpiar_precio(prop.get("Precio S/.")),
        "precio_usd": limpiar_precio(prop.get("Precio USD")),
        "area_m2": calcular_area_m2(prop),
        "dormitorios": normalizar_conteo(prop.get("Habitaciones"), tipo_inmueble),
        "banos": normalizar_conteo(prop.get("Banos"), tipo_inmueble),
        "estacionamientos": parse_num_prefix(prop.get("Cocheras")),
        "distrito": distrito,
        "provincia": provincia,
        "direccion_texto": (prop.get("Ubicacion Full") or "").strip() or None,
        "descripcion": (prop.get("Descripcion") or "").strip() or None,
        "amenities": construir_amenities(prop) or None,
        "latitud": prop.get("Latitud") or None,
        "longitud": prop.get("Longitud") or None,
        "url": prop.get("URL Propiedad") or None,
        "imagen_url": prop.get("Imagen URL") or None,
        "antiguedad_anios": parsear_antiguedad(prop.get("Antiguedad")),
        "agencia_agente": construir_agencia_agente(prop),
    }


CAMPOS_ESTANDAR = [
    "fuente", "id_origen", "fecha_extraccion", "titulo", "tipo_inmueble",
    "tipo_operacion", "precio_soles", "precio_usd", "area_m2", "dormitorios",
    "banos", "estacionamientos", "distrito", "provincia", "direccion_texto",
    "descripcion", "amenities", "latitud", "longitud", "url", "imagen_url",
    "antiguedad_anios", "agencia_agente",
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
        row = estandarizar(prop, fecha_extraccion, "Properati")
        ws_std.append([row.get(c, "") for c in CAMPOS_ESTANDAR])
    for col in ws_std.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws_std.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    # --- Hoja 2: RAW_Original (crudo, tal como venia del scraper) ---
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
    print(f"\n[CHECKPOINT] Guardado -> {OUTPUT_FILE}")
    print(f"  Registros: {len(todas)} | Con coordenadas: {con_coords} | "
          f"Sin coordenadas: {len(todas)-con_coords}")


# =========================================================================
# FUNCIONES DE MAPEO: convierten datos crudos de Properati al formato
# que espera estandarizar() (mismos campos raw que REMAX)
# =========================================================================

def mapear_a_formato_remax(prop):
    """Convierte una propiedad de Properati (formato crudo) al formato raw
    que espera estandarizar() (mismos nombres de campo que REMAX)."""
    # Determinar tipo raw
    tipo_raw = ""
    tipo_prop = (prop.get("Tipo Propiedad") or "").strip()
    titulo = (prop.get("Titulo") or "").strip()

    if tipo_prop:
        tipo_raw = f"{tipo_prop} en Venta"
    elif titulo:
        t_upper = titulo.upper()
        if "DEPARTAMENTO" in t_upper:
            tipo_raw = "Departamento en Venta"
        elif "CASA" in t_upper:
            tipo_raw = "Casa en Venta"
        elif "TERRENO" in t_upper:
            tipo_raw = "Terreno en Venta"
        elif "OFICINA" in t_upper:
            tipo_raw = "Oficina en Venta"
        elif "LOCAL" in t_upper:
            tipo_raw = "Local en Venta"
        else:
            tipo_raw = "Propiedad en Venta"
    else:
        tipo_raw = "Propiedad en Venta"

    # Parsear ubicacion para extraer distrito
    ubicacion = (prop.get("Ubicacion") or "").strip()
    distrito = ""
    provincia = "Arequipa"
    if ubicacion:
        partes = [p.strip() for p in ubicacion.split(",")]
        if len(partes) >= 1:
            for p in partes:
                p_norm = _sin_acentos(p.strip())
                for d in DISTRITOS_AREQUIPA_KNOWN:
                    if _sin_acentos(d) == p_norm or d.lower() in p_norm or p_norm in d.lower():
                        distrito = d
                        break
                if distrito:
                    break
            if not distrito and partes:
                distrito = partes[0]
            if len(partes) >= 2:
                provincia = partes[1]

    # Parsear precios del campo 'Precio' (formato: "S/. 1,234,567 US$ 890,123")
    precio_str = (prop.get("Precio") or "").strip()
    precio_soles = ""
    precio_usd = ""
    if precio_str:
        # Buscar S/. o S/. o S/
        m_soles = re.search(r'(?:S/\.?\s*|S/\s*|Soles?\s*)([\d\',.]+)', precio_str)
        if m_soles:
            precio_soles = m_soles.group(1)
        # Buscar US$ o USD o US$
        m_usd = re.search(r'(?:US[$]?\s*|USD\s*|\$\s*)([\d\',.]+)', precio_str)
        if m_usd:
            precio_usd = m_usd.group(1)

    # Area
    area_raw = (prop.get("Area") or "").strip()

    # Dormitorios, banos
    dorm = (prop.get("Dormitorios") or "").strip()
    banos = (prop.get("Banos") or "").strip()

    # Coordenadas
    lat = prop.get("Latitud") or ""
    lng = prop.get("Longitud") or ""

    return {
        "ID": str(prop.get("ID", "")),
        "Tipo": tipo_raw,
        "Precio S/.": precio_soles,
        "Precio USD": precio_usd,
        "Area Construida": area_raw,
        "Area Terreno": "",
        "Medidas": "",
        "Habitaciones": dorm,
        "Banos": banos,
        "Cocheras": "",
        "Departamento": "Arequipa",
        "Provincia": provincia,
        "Distrito": distrito,
        "Ubicacion Full": ubicacion,
        "Descripcion": (prop.get("Descripcion") or "").strip(),
        "Latitud": lat,
        "Longitud": lng,
        "Coordenadas": f"{lat},{lng}" if lat and lng else "",
        "URL Propiedad": prop.get("URL Propiedad") or "",
        "Imagen URL": prop.get("Imagen URL") or "",
        "Oficina": "",
        "Agente": (prop.get("Agencia") or "").strip(),
        "Serv. Agua": "",
        "Energia Electrica": "",
        "Serv. Drenaje": "",
        "Serv. Gas": "",
        "Antiguedad": "",
        "Pisos": "",
        "Google Maps Link": f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else "",
        # Campos extra para QA
        "Caracteristicas_originales": (prop.get("Caracteristicas") or ""),
        "Fecha_Publicacion_original": (prop.get("Fecha Publicacion") or ""),
        "titulo_original": titulo,
    }


# =========================================================================
# FUNCIONES DE PROPERATI (extraccion)
# =========================================================================

def manejar_sigint(sig, frame):
    """Manejador de Ctrl+C: marca bandera para detener el loop."""
    global detener
    print("\n\n[!] Ctrl+C detectado! Terminando despues de la pagina actual...")
    detener = True


def parsear_fecha_publicacion(texto):
    """
    Convierte texto de fecha de publicacion a un formato estandar.
    Ej: "Publicado hace 2 días" -> "hace 2 días"
    Ej: "Publicado 23 may. 2022" -> "2022-05-23"
    """
    if not texto:
        return texto
    texto = texto.strip()
    if texto.startswith("Publicado "):
        texto = texto[10:]

    meses = {
        'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
    }
    m = re.match(r'(\d+)\s+([a-z]{3})\.?\s*(\d{4})', texto, re.IGNORECASE)
    if m:
        dia = m.group(1).zfill(2)
        mes = meses.get(m.group(2).lower()[:3], '01')
        anio = m.group(3)
        return f"{anio}-{mes}-{dia}"

    return texto


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


def extraer_coordenadas_desde_html(html_content):
    """
    Extrae coordenadas de paginas de detalle de Properati.
    Busca patrones como:
      "latitude": "-14.02852958", "longitude": "-75.73724941"
    """
    match = re.search(
        r'coordinates\s*:\s*\{\s*latitude:\s*"([^"]+)"\s*,\s*longitude:\s*"([^"]+)"',
        html_content
    )
    if match:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -18.5 < lat < -0.1 and -81.5 < lng < -68.5:
                return lat, lng
        except (ValueError, TypeError):
            pass

    jsonld_match = re.search(
        r'"latitude"\s*:\s*(-?\d+\.\d+)\s*,\s*"longitude"\s*:\s*(-?\d+\.\d+)',
        html_content
    )
    if jsonld_match:
        try:
            lat = float(jsonld_match.group(1))
            lng = float(jsonld_match.group(2))
            if -18.5 < lat < -0.1 and -81.5 < lng < -68.5:
                return lat, lng
        except (ValueError, TypeError):
            pass

    return None, None


async def extraer_listado(page):
    """
    Extrae las propiedades de la pagina de listado actual de Properati.
    Las tarjetas son <article class="snippet"> con data-url.
    """
    props = []

    data = await page.evaluate("""
        () => {
            const articles = document.querySelectorAll('article.snippet');
            const results = [];

            for (const article of articles) {
                const dataUrl = article.getAttribute('data-url') || '';
                const idAnuncio = article.getAttribute('data-idanuncio') || '';

                const titleEl = article.querySelector('.title');
                const title = titleEl ? titleEl.textContent.trim() : '';

                const priceEl = article.querySelector('.price');
                const price = priceEl ? priceEl.textContent.trim() : '';

                const locationEl = article.querySelector('.location');
                const location = locationEl ? locationEl.textContent.trim() : '';

                const properties = [];
                article.querySelectorAll('.properties span').forEach(el => {
                    properties.push(el.textContent.trim());
                });
                const features = properties.join(' | ');

                const dateEl = article.querySelector('.published-date');
                const publishedDate = dateEl ? dateEl.textContent.trim() : '';

                const imgEl = article.querySelector('.snippet-main-image, img[src*="img.properati.com"]');
                const imgSrc = imgEl ? imgEl.getAttribute('src') || '' : '';

                const agencyEl = article.querySelector('.agency .name, .agency-name');
                const agency = agencyEl ? agencyEl.textContent.trim() : '';

                results.push({
                    id: idAnuncio,
                    titulo: title,
                    precio: price,
                    ubicacion: location,
                    caracteristicas: features,
                    fecha_publicacion: publishedDate,
                    url: dataUrl,
                    imagen: imgSrc,
                    agencia: agency,
                });
            }
            return results;
        }
    """)

    # Extraer coordenadas del HTML completo de la pagina
    html_content = await page.content()

    jsonld_blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    coords_map = {}
    for block in jsonld_blocks:
        try:
            parsed = json.loads(block)
            items = parsed
            if isinstance(items, dict):
                if '@graph' in items:
                    items = items['@graph']
                else:
                    items = [items]

            if not isinstance(items, list):
                items = [items]

            for item in items:
                if not isinstance(item, dict):
                    continue

                lat = None
                lng = None
                item_url = item.get('url', '')

                location = item.get('location', {})
                if isinstance(location, dict):
                    geo = location.get('geo', {})
                    if isinstance(geo, dict):
                        lat = geo.get('latitude')
                        lng = geo.get('longitude')

                if lat is None:
                    geo = item.get('geo', {})
                    if isinstance(geo, dict):
                        lat = geo.get('latitude')
                        lng = geo.get('longitude')

                if lat is not None and lng is not None:
                    try:
                        lat_f = float(lat)
                        lng_f = float(lng)
                        if -18.5 < lat_f < -0.1 and -81.5 < lng_f < -68.5:
                            if item_url:
                                if item_url.startswith('/'):
                                    item_url = SITE_DOMAIN + item_url
                                if '/detalle/' in item_url:
                                    coords_map[item_url] = {'lat': lat_f, 'lng': lng_f}
                    except (ValueError, TypeError):
                        pass
        except json.JSONDecodeError:
            pass

    # Construir las propiedades
    for item in data:
        if not item['url']:
            continue

        href = item['url']
        if href.startswith('/'):
            href = SITE_DOMAIN + href

        lat = ''
        lng = ''
        coords_str = ''
        maps_link = ''
        if href in coords_map:
            c = coords_map[href]
            lat = c['lat']
            lng = c['lng']
            coords_str = f"{lat},{lng}"
            maps_link = f"https://www.google.com/maps?q={lat},{lng}"

        # Parsear caracteristicas
        feats = item['caracteristicas']
        dormitorios = ''
        banos = ''
        area = ''
        if feats:
            m_dorm = re.search(r'(\d+)\s*(?:hab|dorm|cuartos)', feats, re.IGNORECASE)
            m_bano = re.search(r'(\d+)\s*(?:bañ|ba\u00f1os|banos|ba\u00f1o)', feats, re.IGNORECASE)
            m_area = re.search(r'(\d+[.,]?\d*)\s*m[²2]', feats, re.IGNORECASE)
            if m_dorm: dormitorios = m_dorm.group(1)
            if m_bano: banos = m_bano.group(1)
            if m_area: area = m_area.group(1).replace(',', '.') + ' m²'

        fecha = parsear_fecha_publicacion(item['fecha_publicacion'])

        props.append({
            'ID':              item['id'],
            'Titulo':          item['titulo'],
            'Precio':          item['precio'],
            'Ubicacion':       item['ubicacion'],
            'Caracteristicas': feats,
            'Dormitorios':     dormitorios,
            'Banos':           banos,
            'Area':            area,
            'Fecha Publicacion': fecha,
            'Agencia':         item['agencia'],
            'URL Propiedad':   href,
            'Imagen URL':      item['imagen'],
            'Latitud':         lat,
            'Longitud':        lng,
            'Coordenadas':     coords_str,
            'Google Maps Link': maps_link,
        })

    return props


async def extraer_detalle(page, prop):
    """
    Navega a la ficha de detalle y extrae coordenadas + datos extra.
    """
    url = prop['URL Propiedad']
    if not url:
        return

    if prop.get('Coordenadas'):
        return

    try:
        await navegar_con_cloudflare(page, url, timeout=30)
        await page.wait_for_timeout(2000)

        html_content = await page.content()
        lat, lng = extraer_coordenadas_desde_html(html_content)

        if lat is not None and lng is not None:
            prop['Latitud']          = lat
            prop['Longitud']         = lng
            prop['Coordenadas']      = f"{lat},{lng}"
            prop['Google Maps Link'] = f"https://www.google.com/maps?q={lat},{lng}"
            print(f"   [OK] Coordenadas: {lat}, {lng}")
        else:
            print(f"   [WARN] Sin coordenadas en HTML de detalle")

        # Extraer descripcion completa y otras caracteristicas
        detalles = await page.evaluate("""
            () => {
                const result = {};

                const descEl = document.querySelector('#description-text-full, .description .content');
                if (descEl) result.descripcion = descEl.textContent.replace(/\\s+/g, ' ').trim();

                const facilities = [];
                document.querySelectorAll('.facilities__item span, .facilities__options li span').forEach(el => {
                    const txt = el.textContent.trim();
                    if (txt) facilities.push(txt);
                });
                if (facilities.length > 0) result.caracteristicas_extra = facilities.join(' | ');

                const breadcrumbItems = document.querySelectorAll('.breadcrumb-custom__item a');
                if (breadcrumbItems.length >= 2) {
                    result.tipo_propiedad = breadcrumbItems[1].textContent.trim();
                }

                return result;
            }
        """)

        if detalles:
            if detalles.get('descripcion') and not prop.get('Descripcion'):
                prop['Descripcion'] = detalles['descripcion'][:800]
            if detalles.get('caracteristicas_extra') and not prop.get('Caracteristicas Extra'):
                prop['Caracteristicas Extra'] = detalles['caracteristicas_extra']
            if detalles.get('tipo_propiedad'):
                prop['Tipo Propiedad'] = detalles['tipo_propiedad']

    except Exception as e:
        print(f"   [ERROR] Error en detalle: {e}")
        import traceback
        traceback.print_exc()


async def main():
    global detener
    todas = []

    signal.signal(signal.SIGINT, manejar_sigint)

    async with AsyncCamoufox(
        headless=False,
        os='windows',
        humanize=True,
    ) as browser:

        page = await browser.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})

        # FASE 1: Extraer todas las paginas del listado
        print("=" * 60)
        print("FASE 1: Scrapeando paginas de listado de Properati")
        print(f"Total paginas: {TOTAL_PAGINAS} | Guardando Excel cada {GUARDAR_CADA_N_PAGINAS} paginas")
        print(f"URL base: {BASE_URL}")
        print("Presiona Ctrl+C para guardar y salir")
        print("=" * 60)

        for n in range(1, TOTAL_PAGINAS + 1):
            if detener:
                print(f"\n[!] Deteniendo por solicitud del usuario...")
                break

            if n == 1:
                url = BASE_URL
            else:
                url = f"{BASE_URL}/{n}"

            print(f"\n[Pagina {n}/{TOTAL_PAGINAS}]: {url}")
            try:
                titulo = await navegar_con_cloudflare(page, url)
                print(f"   Titulo: {titulo}")

                props = await extraer_listado(page)
                todas.extend(props)
                print(f"   -> {len(props)} propiedades extraidas (total: {len(todas)})")

                # Guardado periodico cada N paginas
                if n % GUARDAR_CADA_N_PAGINAS == 0 and todas:
                    guardar_excel([mapear_a_formato_remax(p) for p in todas])

            except Exception as e:
                print(f"   [ERROR] en pagina {n}: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n[OK] FASE 1 completa: {len(todas)} propiedades encontradas")

        if not detener and todas:
            # FASE 2: Visitar fichas de detalle para propiedades SIN coordenadas
            sin_coords = [p for p in todas if not p.get('Coordenadas')]
            print(f"\nPropiedades sin coordenadas desde listado: {len(sin_coords)}")

            if sin_coords:
                print("\n" + "=" * 60)
                print("FASE 2: Extrayendo coordenadas desde paginas de detalle")
                print("=" * 60)

                for i, prop in enumerate(sin_coords):
                    if detener:
                        print(f"\n[!] Deteniendo por solicitud del usuario...")
                        break

                    prop_id = prop.get('ID', '')
                    ubic = prop.get('Ubicacion', '')
                    print(f"\n[{i+1}/{len(sin_coords)}] ID: {prop_id} - {ubic}")
                    await extraer_detalle(page, prop)
                    await asyncio.sleep(0.5)

        await page.close()

    # FASE 3: Exportar a Excel (siempre guarda al final)
    print("\n" + "=" * 60)
    print("FASE 3: Exportando Excel")
    print("=" * 60)

    # Convertir todas al formato estandarizado antes de guardar
    todas_estandarizadas = [mapear_a_formato_remax(p) for p in todas]
    guardar_excel(todas_estandarizadas)
    con_coords = sum(1 for p in todas if p.get('Coordenadas'))
    print(f"\n[OK] DESCARGADO -> {OUTPUT_FILE}")
    print(f"Total: {len(todas)} | Con coordenadas: {con_coords} | Sin coordenadas: {len(todas)-con_coords}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupcion por teclado. El Excel se guardo con el progreso actual.")
        sys.exit(0)
