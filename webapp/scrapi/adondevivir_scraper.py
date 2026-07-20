import asyncio
import re
import json
import openpyxl
import signal
import sys
import os
import unicodedata
from datetime import datetime
from camoufox.async_api import AsyncCamoufox

# Forzar UTF-8 en salida estandar (Windows cp1252 no puede con emojis)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "https://www.adondevivir.com"
LISTING_URL = "https://www.adondevivir.com/inmuebles-en-venta-en-arequipa.html"
OUTPUT_FILE = f"adondevivir_arequipa_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
GUARDAR_CADA_N_PAGINAS = 5
PROPS_POR_PAGINA = 30
detener = False


# =========================================================================
# NORMALIZACION / ESTANDARIZACION (compartido con REMAX, Properati, Urbania)
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
    """
    if not texto:
        return None
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


def estandarizar(prop, fecha_extraccion, fuente="ADondevivir"):
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
        row = estandarizar(prop, fecha_extraccion, "ADondevivir")
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
# FUNCIONES DE MAPEO: convierten datos crudos de adondevivir al formato
# que espera estandarizar() (mismos campos raw que REMAX)
# =========================================================================

def mapear_a_formato_remax(prop):
    """Convierte una propiedad de adondevivir (formato crudo) al formato raw
    que espera estandarizar() (mismos nombres de campo que REMAX)."""
    # Determinar tipo raw (adondevivir usa Schema.org types)
    tipo_raw = ""
    tipo_orig = (prop.get("tipo") or "").strip()
    if tipo_orig:
        tipo_upper = tipo_orig.upper()
        if "DEPARTAMENTO" in tipo_upper or "APARTMENT" in tipo_upper:
            tipo_raw = "Departamento en Venta"
        elif "CASA" in tipo_upper or "HOUSE" in tipo_upper or "VILLA" in tipo_upper:
            tipo_raw = "Casa en Venta"
        elif "TERRENO" in tipo_upper or "LOTE" in tipo_upper:
            tipo_raw = "Terreno en Venta"
        elif "OFICINA" in tipo_upper:
            tipo_raw = "Oficina en Venta"
        elif "LOCAL" in tipo_upper:
            tipo_raw = "Local en Venta"
        else:
            tipo_raw = f"{tipo_orig} en Venta"
    else:
        tipo_raw = "Propiedad en Venta"

    # Parsear ubicacion para extraer distrito
    ubicacion = (prop.get("ubicacion") or "").strip()
    distrito = ""
    provincia = "Arequipa"
    if ubicacion:
        partes = [p.strip() for p in ubicacion.split(",")]
        if len(partes) >= 1:
            # Intentar identificar distrito conocido
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

    # Precios: adondevivir ya los tiene separados como enteros
    precio_soles = prop.get("precio_soles") or ""
    precio_usd = prop.get("precio_dolares") or ""
    # Pasar solo el numero puro (sin simbolos de moneda) para que limpiar_precio funcione correctamente
    precio_soles_str = str(precio_soles) if isinstance(precio_soles, (int, float)) and precio_soles else ""
    precio_usd_str = str(precio_usd) if isinstance(precio_usd, (int, float)) and precio_usd else ""

    # Area: adondevivir tiene area (construida) y area_total (terreno)
    area_raw = prop.get("area") or ""
    area_total_raw = prop.get("area_total") or ""

    # Dormitorios, banos, estacionamientos
    dorm = prop.get("dormitorios") or ""
    banos = prop.get("banos") or ""
    estac = prop.get("estacionamientos") or ""

    # Coordenadas
    lat = prop.get("latitud") or ""
    lng = prop.get("longitud") or ""

    return {
        "ID": str(prop.get("id", "")),
        "Tipo": tipo_raw,
        "Precio S/.": precio_soles_str,
        "Precio USD": precio_usd_str,
        "Area Construida": str(area_raw),
        "Area Terreno": str(area_total_raw),
        "Medidas": "",
        "Habitaciones": str(dorm),
        "Banos": str(banos),
        "Cocheras": str(estac),
        "Departamento": "Arequipa",
        "Provincia": provincia,
        "Distrito": distrito,
        "Ubicacion Full": ubicacion,
        "Descripcion": (prop.get("descripcion") or "").strip(),
        "Latitud": lat,
        "Longitud": lng,
        "Coordenadas": f"{lat},{lng}" if lat and lng else "",
        "URL Propiedad": prop.get("url") or "",
        "Imagen URL": "",
        "Oficina": "",
        "Agente": (prop.get("publicado_por") or "").strip(),
        "Serv. Agua": "",
        "Energia Electrica": "",
        "Serv. Drenaje": "",
        "Serv. Gas": "",
        "Antiguedad": "",
        "Pisos": "",
        "Google Maps Link": f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else "",
        # Campo extra para QA
        "tipo_publicacion_original": (prop.get("tipo_publicacion") or ""),
        "titulo_original": (prop.get("titulo") or ""),
    }


# =========================================================================
# FUNCIONES DE ADONDEVIVIR (extraccion)
# =========================================================================

def manejar_sigint(sig, frame):
    global detener
    print("\n\n[!] Recibida senal de interrupcion. Terminando despues de la pagina actual...")
    detener = True


async def esperar_cloudflare(page, timeout=30):
    """Espera a que Cloudflare resuelva el challenge."""
    start = __import__('time').time()
    while __import__('time').time() - start < timeout:
        try:
            title = await page.title()
            if "cloudflare" not in title.lower() and "just a moment" not in title.lower():
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


async def navegar_con_cloudflare(page, url, timeout=30):
    """Navega a una URL esperando que Cloudflare se resuelva."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await esperar_cloudflare(page, timeout)
        await asyncio.sleep(3)
        return True
    except Exception as e:
        print(f"  [!] Error navegando: {e}")
        return False


def parsear_precio_soles_dolares(texto):
    """Extrae precios en Soles y Dolares del texto de precio."""
    soles = None
    dolares = None
    if not texto:
        return soles, dolares
    texto = texto.strip()

    patron_soles = r'(?:S/\.?\s*)([\d,]+)'
    match_soles = re.search(patron_soles, texto)
    if match_soles:
        try:
            soles = int(match_soles.group(1).replace(",", ""))
        except ValueError:
            pass

    patron_dolares = r'(?:US[$]|USD)\s*([\d,]+)'
    match_dolares = re.search(patron_dolares, texto)
    if match_dolares:
        try:
            dolares = int(match_dolares.group(1).replace(",", ""))
        except ValueError:
            pass

    if soles is None and dolares is None:
        numeros = re.findall(r'([\d,]+)', texto)
        valores = []
        for n in numeros:
            try:
                valores.append(int(n.replace(",", "")))
            except ValueError:
                pass
        if len(valores) >= 1:
            soles = valores[0]
        if len(valores) >= 2:
            dolares = valores[1]

    return soles, dolares


def decodificar_coordenadas(base64_str):
    """Decodifica coordenadas en base64 (formato usado por Navent/Adondevivir)."""
    try:
        import base64
        decoded = base64.b64decode(base64_str).decode('utf-8')
        return decoded
    except Exception:
        return None


async def extraer_coordenadas_desde_detalle(page, url):
    """Navega a una pagina de detalle y extrae coordenadas de mapLatOf/mapLngOf (base64)."""
    exito = await navegar_con_cloudflare(page, url, timeout=30)
    if not exito:
        return None, None, ""

    await asyncio.sleep(2)

    tipo_prop = ""

    try:
        html_content = await page.content()

        # --- Extraer tipo de propiedad ---
        tipo_match = re.search(
            r'<h2[^>]*class="[^"]*title-type-sup-property[^"]*"[^>]*>\s*([^<]+?)\s*</h2>',
            html_content
        )
        if tipo_match:
            texto_tipo = tipo_match.group(1).strip()
            tipo_prop = texto_tipo.split("\u00b7")[0].split("·")[0].strip()

        if not tipo_prop:
            bread_match = re.search(
                r'<a\s+href="/[^/]+\.html"[^>]*>\s*([A-Za-z]+)\s*</a>',
                html_content
            )
            if bread_match:
                tipo_prop = bread_match.group(1).strip()

        if not tipo_prop:
            re_match = re.search(
                r"'realEstateType':\s*\{\s*\"name\":\s*\"([^\"]+)\"",
                html_content
            )
            if re_match:
                tipo_prop = re_match.group(1).strip()

        # --- Extraer coordenadas ---
        lat, lng = None, None

        lat_match = re.search(r'mapLatOf\s*=\s*"([^"]+)"', html_content)
        lng_match = re.search(r'mapLngOf\s*=\s*"([^"]+)"', html_content)

        if lat_match and lng_match:
            lat_b64 = lat_match.group(1)
            lng_b64 = lng_match.group(1)
            lat = decodificar_coordenadas(lat_b64)
            lng = decodificar_coordenadas(lng_b64)

        if not lat or not lng:
            patron_geo = r'"latitude"\s*:\s*"([^"]+)"\s*,\s*"longitude"\s*:\s*"([^"]+)"'
            geo_match = re.search(patron_geo, html_content)
            if geo_match:
                lat = geo_match.group(1)
                lng = geo_match.group(2)

        return lat, lng, tipo_prop

    except Exception as e:
        print(f"    [!] Error extrayendo coordenadas de detalle: {e}")

    return None, None, tipo_prop


def mapear_tipo_schemaorg(tipo_schema):
    """Mapea tipos Schema.org a labels del portal."""
    if not tipo_schema:
        return ""
    tipo_lower = tipo_schema.lower()
    if "apartment" in tipo_lower:
        return "Departamento"
    if "house" in tipo_lower or "singlefamily" in tipo_lower:
        return "Casa"
    if "accommodation" in tipo_lower and "apartment" not in tipo_lower and "house" not in tipo_lower:
        return "Alojamiento"
    return tipo_schema


async def extraer_listado(page):
    """Extrae todas las propiedades de la pagina actual del listado."""
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(3)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(2)

    cards_data = await page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-qa^="posting"]');
            const results = [];

            cards.forEach(card => {
                const dataId = card.getAttribute('data-id') || '';
                const postingType = card.getAttribute('data-posting-type') || '';
                const toPosting = card.getAttribute('data-to-posting') || '';

                const priceEl = card.querySelector('[data-qa="POSTING_CARD_PRICE"]');
                const priceText = priceEl ? priceEl.textContent.trim() : '';

                let precioSoles = '', precioDolares = '';
                if (priceEl) {
                    const spans = priceEl.querySelectorAll('span');
                    spans.forEach(sp => {
                        const t = sp.textContent.trim();
                        if (t.startsWith('S/') || t.startsWith('S/.')) {
                            precioSoles = t;
                        } else if (t.startsWith('US$') || t.startsWith('USD')) {
                            precioDolares = t;
                        }
                    });
                }

                const featuresEl = card.querySelector('[data-qa="POSTING_CARD_FEATURES"]');
                let area = '', dormitorios = '', banos = '', estacionamientos = '', areaTotal = '';
                if (featuresEl) {
                    const featureItems = featuresEl.querySelectorAll('li');
                    featureItems.forEach(item => {
                        const text = item.textContent.trim();
                        const lower = text.toLowerCase();
                        if (lower.includes('m²') || lower.includes('m2')) {
                            if (lower.includes('total')) {
                                areaTotal = text;
                            } else {
                                area = text;
                            }
                        } else if (lower.includes('dorm') || lower.includes('habitac')) {
                            dormitorios = text;
                        } else if (lower.includes('bañ') || lower.includes('ban')) {
                            banos = text;
                        } else if (lower.includes('estacion')) {
                            estacionamientos = text;
                        }
                    });
                }

                const locationEl = card.querySelector('[data-qa="POSTING_CARD_LOCATION"]');
                const location = locationEl ? locationEl.textContent.trim() : '';

                const descEl = card.querySelector('[data-qa="POSTING_CARD_DESCRIPTION"]');
                const description = descEl ? descEl.textContent.trim() : '';

                const publisherEl = card.querySelector('[data-qa="POSTING_CARD_PUBLISHER"]');
                let publisher = '';
                if (publisherEl) {
                    const img = publisherEl.querySelector('img');
                    publisher = img ? (img.getAttribute('alt') || img.getAttribute('title') || '') : publisherEl.textContent.trim();
                }
                const publisherDevEl = card.querySelector('[data-qa="POSTING_CARD_PUBLISHER_DEV"]');
                let publisherDev = '';
                if (publisherDevEl) {
                    const img = publisherDevEl.querySelector('img');
                    publisherDev = img ? (img.getAttribute('alt') || img.getAttribute('title') || '') : publisherDevEl.textContent.trim();
                }

                let title = '';
                const linkEl = card.querySelector('a[href*="/propiedades/"]');
                if (linkEl) {
                    title = linkEl.getAttribute('title') || linkEl.textContent.trim();
                }

                const url = toPosting ? 'https://www.adondevivir.com' + toPosting : '';

                let lat = '', lng = '', tipoSchema = '';
                const script = card.querySelector('script[type="application/ld+json"]');
                if (script) {
                    try {
                        const data = JSON.parse(script.textContent);
                        if (data['@type'] === 'SellAction') {
                            const obj = data.object || {};
                            if (obj.geo && obj.geo.type === 'GeoCoordinates') {
                                lat = obj.geo.latitude || '';
                                lng = obj.geo.longitude || '';
                            }
                            if (obj.type) {
                                tipoSchema = obj.type.split('/')[0].trim();
                            }
                            if (!title && obj.name) title = obj.name;
                            if (!description && obj.description) description = obj.description;
                            if (!dormitorios && obj.numberOfBedrooms) dormitorios = String(obj.numberOfBedrooms);
                            if (!banos && obj.numberOfBathroomsTotal) banos = String(obj.numberOfBathroomsTotal);
                            if (!area && obj.floorSize && obj.floorSize.unitText) area = obj.floorSize.unitText;
                        }
                    } catch(e) {}
                }

                results.push({
                    id: dataId,
                    tipo_publicacion: postingType,
                    titulo: title,
                    tipo: tipoSchema,
                    precio_texto: priceText,
                    precio_soles: precioSoles,
                    precio_dolares: precioDolares,
                    url: url,
                    ubicacion: location,
                    descripcion: description,
                    publicado_por: publisher || publisherDev,
                    area: area,
                    area_total: areaTotal,
                    dormitorios: dormitorios,
                    banos: banos,
                    estacionamientos: estacionamientos,
                    latitud: lat,
                    longitud: lng
                });
            });

            return results;
        }
    """)

    for card in cards_data:
        soles_str = card.get("precio_soles", "")
        dolares_str = card.get("precio_dolares", "")
        texto = card.get("precio_texto", "")

        if not soles_str and not dolares_str:
            soles_val, dolares_val = parsear_precio_soles_dolares(texto)
            card["precio_soles"] = soles_val
            card["precio_dolares"] = dolares_val
        else:
            if soles_str:
                m = re.search(r'[\d,]+', str(soles_str))
                if m:
                    try:
                        card["precio_soles"] = int(m.group().replace(",", ""))
                    except ValueError:
                        card["precio_soles"] = None
            if dolares_str:
                m = re.search(r'[\d,]+', str(dolares_str))
                if m:
                    try:
                        card["precio_dolares"] = int(m.group().replace(",", ""))
                    except ValueError:
                        card["precio_dolares"] = None

        del card["precio_texto"]

    print(f"  Cards: {len(cards_data)}")
    with_coords = sum(1 for c in cards_data if c.get("latitud") and c.get("longitud"))
    print(f"  Con coordenadas: {with_coords}")

    return cards_data


async def obtener_numero_paginas(page):
    """Obtiene el numero total de paginas del listado."""
    html_content = await page.content()

    patron_paginas = r'data-qa="PAGING_(\d+)"'
    matches = re.findall(patron_paginas, html_content)

    if matches:
        nums = [int(p) for p in matches]
        max_paging = max(nums)
        total_props = await obtener_total_propiedades(page)
        if total_props:
            paginas_calculadas = (total_props + PROPS_POR_PAGINA - 1) // PROPS_POR_PAGINA
            if paginas_calculadas > max_paging:
                print(f"  (Calculado desde total de {total_props} props: {paginas_calculadas} paginas)")
                return paginas_calculadas
        return max_paging

    total_props = await obtener_total_propiedades(page)
    if total_props:
        paginas = (total_props + PROPS_POR_PAGINA - 1) // PROPS_POR_PAGINA
        print(f"  (Calculado desde total de {total_props} props: {paginas} paginas)")
        return paginas

    return 30


async def obtener_total_propiedades(page):
    """Obtiene el total de propiedades del texto del listado."""
    try:
        texto = await page.evaluate("() => document.body.innerText")
        patron = r'(\d[\d,]*)\s*propiedades?'
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(',', ''))
    except Exception:
        pass

    try:
        html_content = await page.content()
        patron = r'(\d[\d,]*)\s*propiedades?'
        match = re.search(patron, html_content, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(',', ''))
    except Exception:
        pass

    return None


async def main():
    signal.signal(signal.SIGINT, manejar_sigint)
    global detener

    todas_las_propiedades = []

    print("=" * 70)
    print("SCRAPER ADONDEVIVIR - Arequipa")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    async with AsyncCamoufox(headless=False, os='windows', humanize=True) as browser:
        context = await browser.new_context()
        page = await context.new_page()

        # ============================================================
        # FASE 1: Extraer listado completo
        # ============================================================
        print(f"\n{'=' * 70}")
        print(f"FASE 1: Extrayendo listado de propiedades...")
        print(f"{'=' * 70}")

        print(f"\n[Pagina 1] Navegando...")
        await navegar_con_cloudflare(page, LISTING_URL, timeout=30)

        total_paginas = await obtener_numero_paginas(page)
        print(f"Total de paginas detectadas: {total_paginas}")

        print(f"\n[Pagina 1] Extrayendo...")
        props = await extraer_listado(page)
        todas_las_propiedades.extend(props)
        print(f"  [OK] Pagina 1: {len(props)} props (total: {len(todas_las_propiedades)})")

        if detener:
            guardar_excel([mapear_a_formato_remax(p) for p in todas_las_propiedades])
            return

        for pagina in range(2, total_paginas + 1):
            if detener:
                break

            url_pagina = f"https://www.adondevivir.com/inmuebles-en-venta-en-arequipa-pagina-{pagina}.html"
            print(f"\n[Pagina {pagina}] Navegando...")

            exito = await navegar_con_cloudflare(page, url_pagina, timeout=30)
            if not exito:
                print(f"  [!] Error al cargar pagina {pagina}, saltando...")
                continue

            props = await extraer_listado(page)
            todas_las_propiedades.extend(props)
            print(f"  [OK] Pagina {pagina}: {len(props)} props (total: {len(todas_las_propiedades)})")

            if pagina % GUARDAR_CADA_N_PAGINAS == 0:
                print(f"\n[Guardado] Automatico (pagina {pagina})...")
                guardar_excel([mapear_a_formato_remax(p) for p in todas_las_propiedades])

        # ============================================================
        # FASE 2: Visitar detalles para propiedades sin coordenadas
        # ============================================================
        props_a_visitar = [p for p in todas_las_propiedades
                          if not p.get("latitud") or not p.get("longitud")
                          or not p.get("tipo")]

        if props_a_visitar and not detener:
            print(f"\n{'=' * 70}")
            print(f"FASE 2: Visitando {len(props_a_visitar)} detalles (coordenadas + tipo)...")
            print(f"{'=' * 70}")

            for i, prop in enumerate(props_a_visitar, 1):
                if detener:
                    break

                url = prop.get("url", "")
                if not url:
                    print(f"  [{i}/{len(props_a_visitar)}] Sin URL, saltando...")
                    continue

                print(f"  [{i}/{len(props_a_visitar)}] Visitando detalle...")
                lat, lng, tipo_prop = await extraer_coordenadas_desde_detalle(page, url)

                cambios = []
                if lat and lng:
                    prop["latitud"] = lat
                    prop["longitud"] = lng
                    cambios.append(f"coords={lat},{lng}")
                if tipo_prop:
                    prop["tipo"] = tipo_prop
                    cambios.append(f"tipo={tipo_prop}")

                if cambios:
                    print(f"    [OK] {'; '.join(cambios)}")
                else:
                    print(f"    [!] No se encontraron datos adicionales")

                if i % 10 == 0:
                    print(f"\n[Guardado] Automatico ({i} detalles visitados)...")
                    guardar_excel([mapear_a_formato_remax(p) for p in todas_las_propiedades])

    # Post-procesamiento: mapear tipos Schema.org
    for prop in todas_las_propiedades:
        if prop.get("tipo") and not any(palabra in prop["tipo"] for palabra in ["Casa", "Departamento", "Terreno", "Local", "Oficina", "Alojamiento"]):
            prop["tipo"] = mapear_tipo_schemaorg(prop["tipo"])

    # Final
    print(f"\n{'=' * 70}")
    print(f"RESUMEN FINAL")
    print(f"{'=' * 70}")
    print(f"Total propiedades extraidas: {len(todas_las_propiedades)}")

    with_coords = sum(1 for p in todas_las_propiedades if p.get("latitud") and p.get("longitud"))
    print(f"Propiedades con coordenadas: {with_coords}")

    if todas_las_propiedades:
        # Convertir todas al formato estandarizado antes de guardar
        todas_estandarizadas = [mapear_a_formato_remax(p) for p in todas_las_propiedades]
        guardar_excel(todas_estandarizadas)

    print(f"\n[OK] Scraping completado!")
    print(f"Archivo: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Proceso interrumpido por el usuario.")
    except Exception as e:
        print(f"\n[ERROR] General: {e}")
        import traceback
        traceback.print_exc()
