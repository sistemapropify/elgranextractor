import asyncio
import re
import unicodedata
import openpyxl
import signal
import sys
from datetime import datetime
from camoufox.async_api import AsyncCamoufox

BASE_URL = "https://www.remax.pe/web/search/all/propertys/list/?departament__in=4&page={}"
SITE_DOMAIN = "https://www.remax.pe"
TOTAL_PAGES = 32
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
    solo_numeros = re.sub(r"[^\d.,]", "", str(texto))  # descarta S/, USD, comillas, espacios
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
    """REMAX no trae titulo propio: se sintetiza uno a partir del tipo/operacion/distrito."""
    partes = [p for p in (tipo_inmueble, f"en {operacion}" if operacion else None,
                           f"- {distrito}" if distrito else None) if p]
    return " ".join(partes) if partes else None


def estandarizar(prop, fecha_extraccion):
    """Convierte un registro crudo de REMAX al esquema estandarizado comun."""
    tipo_raw = prop.get("Tipo", "")
    tipo_inmueble = clasificar_tipo_inmueble(tipo_raw)
    operacion = clasificar_operacion(tipo_raw)
    distrito = normalizar_ubicacion(prop.get("Distrito"))
    provincia = normalizar_ubicacion(prop.get("Provincia"))

    return {
        "fuente": "REMAX",
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
    await esperar_cloudflare(page, timeout)
    await page.wait_for_timeout(1000)
    return await page.title()


async def extraer_listado(page):
    """Extrae propiedades de la pagina de listado actual con los selectores originales."""
    props = []
    cards = await page.query_selector_all('.__propiedadgen')

    for card in cards:
        try:
            id_el    = await card.query_selector('.badge-danger-xs')
            link_el  = await card.query_selector('.__imagen a')
            img_el   = await card.query_selector('.__imagen img')
            tipo_el  = await card.query_selector('.badge-blue-xs')
            wa_el    = await card.query_selector('.__agenteproint a[href*="wa.me"]')
            precio_els = await card.query_selector_all('.__casventap li')
            ubic_els   = await card.query_selector_all('.__casadat h5')

            precios = []
            for p in precio_els:
                t = (await p.inner_text()).strip()
                if t != '-':
                    precios.append(t)

            feats = {}
            feat_els = await card.query_selector_all('.__icofeat')
            for f in feat_els:
                p_el = await f.query_selector('p')
                if p_el:
                    txt = (await p_el.inner_text()).strip()
                    m = re.match(r'(.+?)\s*:\s*(.+)', txt)
                    if m:
                        feats[m.group(1).strip()] = m.group(2).strip()

            wa_href  = await wa_el.get_attribute('href') if wa_el else ''
            tel_m    = re.search(r'wa\.me\/(\d+)', wa_href) if wa_href else None
            ubic_raw = (await ubic_els[0].inner_text()) if ubic_els else ''
            ubic     = re.sub(r'\s+', ' ', ubic_raw).strip()
            parts    = [s.strip() for s in ubic.split(',')]

            # Convertir URL relativa a absoluta
            href_raw = await link_el.get_attribute('href') if link_el else ''
            if href_raw and href_raw.startswith('/'):
                href_raw = SITE_DOMAIN + href_raw

            img_src = await img_el.get_attribute('src') if img_el else ''
            if img_src and img_src.startswith('/'):
                img_src = SITE_DOMAIN + img_src

            props.append({
                'ID':               (await id_el.inner_text()).strip() if id_el else '',
                'Tipo':             (await tipo_el.inner_text()).strip() if tipo_el else '',
                'Precio S/.':       precios[0] if len(precios) > 0 else '',
                'Precio USD':       precios[1] if len(precios) > 1 else '',
                'Departamento':     parts[0] if len(parts) > 0 else '',
                'Provincia':        parts[1] if len(parts) > 1 else '',
                'Distrito':         parts[2] if len(parts) > 2 else '',
                'Ubicacion Full':   ubic,
                'Oficina':          '',
                'Agente':           '',
                'Telefono':         tel_m.group(1) if tel_m else '',
                'Area Terreno':     feats.get('Area Terreno', ''),
                'Area Construida':  feats.get('Area Construida', ''),
                'Pisos':            feats.get('Pisos', ''),
                'Habitaciones':     feats.get('Habitaciones', ''),
                'Banos':            feats.get('Banos', ''),
                'Cocheras':         feats.get('Cocheras', ''),
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
            print(f"  [WARN] Error en card: {e}")

    return props


async def extraer_detalle(page, prop):
    """Navega a la ficha de detalle y extrae coordenadas + campos extras."""
    url = prop['URL Propiedad']
    if not url:
        return

    try:
        await navegar_con_cloudflare(page, url, timeout=30)
        # Esperar a que Leaflet inicialice el mapa
        await page.wait_for_timeout(2000)

        # Coordenadas: leer el objeto map de Leaflet desde JS
        coords = await page.evaluate("""
            () => {
                // Metodo 1: variable global 'map'
                if (typeof map !== 'undefined' && map && map.getCenter) {
                    const c = map.getCenter();
                    return { lat: c.lat, lng: c.lng };
                }
                // Metodo 2: buscar instancia Leaflet en window
                for (const key of Object.keys(window)) {
                    try {
                        const obj = window[key];
                        if (obj && typeof obj === 'object' && obj.getCenter && obj._container) {
                            const c = obj.getCenter();
                            return { lat: c.lat, lng: c.lng };
                        }
                    } catch(e) {}
                }
                // Metodo 3: buscar setView en scripts
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const m = s.textContent.match(/setView\\(\\[([-\\d.]+)\\s*,\\s*([-\\d.]+)\\]/);
                    if (m) return { lat: parseFloat(m[1]), lng: parseFloat(m[2]) };
                }
                return null;
            }
        """)

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
        if get('Area Libre'):      pass  # campo extra opcional
        if get('Area Ocupada'):    pass  # campo extra opcional

        # Descripcion
        desc_el = await page.query_selector('.__text_match')
        if desc_el:
            prop['Descripcion'] = (await desc_el.inner_text()).replace('\n', ' ').strip()[:800]

        # Fecha de publicacion
        fecha_el = await page.query_selector('.titulo_02')
        if fecha_el:
            texto_fecha = (await fecha_el.inner_text()).strip()
            if 'Publicado' in texto_fecha or 'publicado' in texto_fecha:
                prop['Fecha Publicacion'] = texto_fecha.replace('Publicado el :', '').replace('Publicado el:', '').strip()

        # Agente y oficina
        agente_els = await page.query_selector_all('.__casadat h5')
        if len(agente_els) > 1:
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
        prop['Google Maps Link'] = f"https://www.google.com/maps/search/?api=1&query={prop['Ubicacion Full'].replace(' ', '+')}"


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
        user_data_dir='./camoufox_session',
    ) as browser:

        page = await browser.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})

        # FASE 1: Extraer todas las paginas del listado
        print("=" * 60)
        print("FASE 1: Scrapeando paginas de listado")
        print(f"Total paginas: {TOTAL_PAGES} | Guardando Excel cada {GUARDAR_CADA_N_PAGINAS} paginas")
        print("Presiona Ctrl+C para guardar y salir")
        print("=" * 60)

        for n in range(1, TOTAL_PAGES + 1):
            if detener:
                print(f"\n[!] Deteniendo por solicitud del usuario...")
                break

            url = BASE_URL.format(n)
            print(f"\n[Pagina {n}/{TOTAL_PAGES}]: {url}")
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

                distrito = prop.get('Distrito', '')
                prop_id = prop.get('ID', '')
                print(f"\n[{i+1}/{len(todas)}] ID: {prop_id} - {distrito}")
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