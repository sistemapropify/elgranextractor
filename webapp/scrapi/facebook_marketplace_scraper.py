"""Extraccion publica de Facebook Marketplace mediante Camoufox.

No usa endpoints GraphQL privados ni intenta revelar ``[hidden information]``.
Los selectores se apoyan en la URL estable ``/marketplace/item/<id>`` y en
contenido visible para resistir cambios de clases CSS generadas por Facebook.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from captura.azure_storage import upload_bytes
from scrapi.camoufox_launcher import camoufox_kwargs, is_headless_server
from scrapi.normalization import operation, number, validate_row
from scrapi.contracts import Discovery, ScrapeRows, ScrapingInterrupted
from scrapi.source_config import validate_url


DEFAULT_SEARCH_URL = os.environ.get(
    "FACEBOOK_MARKETPLACE_SEARCH_URL",
    "https://www.facebook.com/marketplace/110200712339125/search/"
    "?query=Viviendas%20en%20venta&category_id=1270772586445798"
    "&exact=false&radius=65&referral_ui_component=category_menu_item"
    "&locale=es_LA",
)
DEFAULT_MAX_ITEMS = int(os.environ.get("FACEBOOK_MARKETPLACE_MAX_ITEMS", "1500"))
SESSION_COOKIES_JSON = os.environ.get(
    "FACEBOOK_MARKETPLACE_COOKIES_JSON", ""
).strip()

DEFAULT_IDLE_SCROLLS = int(os.environ.get("FACEBOOK_MARKETPLACE_IDLE_SCROLLS", "15"))
MIN_SCROLL_ROUNDS = int(os.environ.get("FACEBOOK_MARKETPLACE_MIN_SCROLL_ROUNDS", "20"))
MAX_SCROLL_ROUNDS = int(os.environ.get("FACEBOOK_MARKETPLACE_MAX_SCROLL_ROUNDS", "250"))
SCROLL_WAIT_MS = int(os.environ.get("FACEBOOK_MARKETPLACE_SCROLL_WAIT_MS", "2600"))
SCROLL_WHEEL_BURST = int(os.environ.get("FACEBOOK_MARKETPLACE_SCROLL_WHEEL_BURST", "4"))
DETAIL_WAIT_MS = int(os.environ.get("FACEBOOK_MARKETPLACE_DETAIL_WAIT_MS", "900"))
LOGIN_WAIT_SECONDS = int(os.environ.get("FACEBOOK_MARKETPLACE_LOGIN_WAIT_SECONDS", "600"))
MAX_IMAGES_PER_ITEM = int(os.environ.get("FACEBOOK_MARKETPLACE_MAX_IMAGES_PER_ITEM", "20"))
TOTAL_TIMEOUT = int(os.environ.get("FACEBOOK_MARKETPLACE_TOTAL_TIMEOUT", "10800"))
PROFILE_DIR = os.environ.get(
    "FACEBOOK_MARKETPLACE_PROFILE_DIR",
    (
        "/home/data/camoufox_session_facebook_marketplace"
        if os.name != "nt"
        else str(Path("camoufox_session_facebook_marketplace"))
    ),
)

ITEM_RE = re.compile(r"/marketplace/item/(\d+)", re.IGNORECASE)
PRICE_RE = re.compile(r"^(S/|US\$|\$)\s*([\d.,]+)\b", re.IGNORECASE)
COORD_RE = re.compile(r"center=(-?\d+(?:\.\d+)?)%?2C(-?\d+(?:\.\d+)?)", re.I)

AREQUIPA_CENTER = (-16.409047, -71.537451)
AREQUIPA_RADIUS_KM = float(os.environ.get("FACEBOOK_MARKETPLACE_RADIUS_KM", "65"))
AREQUIPA_LOCATIONS = (
    "arequipa", "alto selva alegre", "cayma", "cerro colorado",
    "characato", "chiguata", "jacobo hunter", "jose luis bustamante y rivero",
    "la joya", "mariano melgar", "miraflores", "mollebaya", "paucarpata",
    "pocsi", "polobaya", "quequena", "sabandia", "sachaca",
    "san juan de siguas", "san juan de tarucani", "santa isabel de siguas",
    "santa rita de siguas", "socabaya", "tiabaya", "uchumayo", "vitor",
    "yanahuara", "yarabamba", "yura",
)
OUTSIDE_AREQUIPA_LOCATIONS = (
    "tacna", "juliaca", "puno", "cusco", "moquegua", "ilo", "lima",
    "ica", "ayacucho", "abancay", "huancayo",
)


def _running_headless():
    return is_headless_server() or os.environ.get("CAMOUFOX_HEADLESS") == "1"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _number(value: str) -> float | None:
    raw = re.sub(r"[^\d.,]", "", value or "")
    if not raw:
        return None
    if "." in raw and "," in raw:
        decimal = "." if raw.rfind(".") > raw.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        raw = raw.replace(thousands, "").replace(decimal, ".")
    elif raw.count(".") == 1 and len(raw.rsplit(".", 1)[1]) == 3:
        raw = raw.replace(".", "")
    elif raw.count(",") == 1 and len(raw.rsplit(",", 1)[1]) == 3:
        raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def classify_arequipa_location(location: str | None) -> bool | None:
    """True=Arequipa, False=otra ciudad, None=ubicación insuficiente."""
    normalized = _plain(_clean(location))
    if not normalized:
        return None
    if any(
        re.search(rf"\b{re.escape(name)}\b", normalized)
        for name in OUTSIDE_AREQUIPA_LOCATIONS
    ):
        return False
    if any(
        re.search(rf"\b{re.escape(name)}\b", normalized)
        for name in AREQUIPA_LOCATIONS
    ):
        return True
    return None


def _distance_from_arequipa_km(latitude: Any, longitude: Any) -> float | None:
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    center_lat, center_lng = AREQUIPA_CENTER
    lat1, lat2 = math.radians(center_lat), math.radians(lat)
    delta_lat = math.radians(lat - center_lat)
    delta_lng = math.radians(lng - center_lng)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(haversine)))


def is_arequipa_item(item: dict[str, Any], radius_km=None) -> bool:
    """Valida el radio de 65 km o, sin mapa, un distrito de Arequipa."""
    distance = _distance_from_arequipa_km(
        item.get("latitude"), item.get("longitude")
    )
    if distance is not None:
        return distance <= (AREQUIPA_RADIUS_KM if radius_km is None else radius_km)
    return classify_arequipa_location(item.get("location")) is True


def parse_price(text: str) -> dict[str, Any]:
    text = _clean(text)
    if _plain(text).startswith("gratis"):
        return {"raw": "Gratis", "currency": None, "amount": None, "quality": "placeholder"}
    match = PRICE_RE.search(text)
    if not match:
        return {"raw": None, "currency": None, "amount": None, "quality": "missing"}
    symbol, amount_raw = match.groups()
    currency = "PEN" if symbol.upper().startswith("S/") else "USD"
    amount = _number(amount_raw)
    quality = "placeholder" if amount in (0, 1) else "reported"
    return {
        "raw": f"{symbol}{amount_raw}",
        "currency": currency,
        "amount": amount,
        "quality": quality,
    }


def infer_property_type(*values: str) -> str:
    text = _plain(" ".join(v or "" for v in values))
    patterns = (
        ("Terreno", ("terreno", "lote")),
        ("Departamento", ("departamento", "depa ", "duplex", "dúplex", "flat")),
        ("Casa", ("casa", "vivienda", "chalet")),
        ("Local", ("local comercial", "tienda", "almacen", "almacén")),
        ("Oficina", ("oficina", "consultorio")),
        ("Hotel", ("hotel", "hostal")),
    )
    for result, words in patterns:
        if any(word in text for word in words):
            return result
    return "Otro"


def _location_from_alt(alt: str, title: str) -> str | None:
    alt = _clean(alt)
    if not alt:
        return None
    if alt.lower().startswith("foto "):
        return None
    candidate = re.sub(r"^" + re.escape(_clean(title)) + r"\s+en\s+", "", alt, flags=re.I)
    candidate = re.sub(r",\s*AR$", "", candidate, flags=re.I)
    return candidate if candidate != alt and candidate else None


def parse_listing_html(html: str) -> list[dict[str, Any]]:
    """Extrae y deduplica las tarjetas actualmente presentes en el DOM."""
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = ITEM_RE.search(anchor.get("href", ""))
        if not match or match.group(1) in seen:
            continue
        item_id = match.group(1)
        seen.add(item_id)
        text = _clean(anchor.get_text(" ", strip=True))
        image = next(
            (img for img in anchor.find_all("img") if str(img.get("src", "")).startswith("http")),
            None,
        )
        alt = _clean(image.get("alt")) if image else ""
        location = None
        title = alt
        if alt:
            location_match = re.match(r"^(.*)\s+en\s+(.+?),\s*AR$", alt, re.I)
            if location_match:
                title = location_match.group(1).strip()
                location = location_match.group(2).strip()
        price = parse_price(text)
        if not title:
            title = text
            if price.get("raw"):
                title = title[len(price["raw"]):].strip()
            title = re.sub(r"^Reci[eé]n publicado\s+", "", title, flags=re.I)
        items.append({
            "id": item_id,
            "url": f"https://www.facebook.com/marketplace/item/{item_id}/",
            "title": title or f"Marketplace {item_id}",
            "location": location,
            "price": price,
            "image_url": image.get("src") if image else None,
            "card_text": text,
            "recently_published": bool(re.search(r"reci[eé]n publicado", text, re.I)),
        })
    return items


def _coordinates_from_soup(soup: BeautifulSoup) -> tuple[float | None, float | None, str | None]:
    for image in soup.find_all("img", src=True):
        src = unquote(str(image.get("src", "")))
        if "static_map.php" not in src:
            continue
        parsed = urlparse(src)
        center = parse_qs(parsed.query).get("center", [""])[0]
        match = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", center)
        if not match:
            match = COORD_RE.search(src)
        if match:
            return float(match.group(1)), float(match.group(2)), str(image.get("src"))
    return None, None, None


def parse_detail_html(html: str, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extrae exclusivamente información visible de una ficha de Marketplace."""
    seed = dict(seed or {})
    soup = BeautifulSoup(html or "", "html.parser")
    visible = _clean(soup.get_text(" ", strip=True))
    title = _clean((soup.title.string if soup.title and soup.title.string else ""))
    if not title or "facebook" in title.lower() or title.lower() == "marketplace":
        title = seed.get("title") or ""
    price = parse_price(visible)
    if not price.get("raw"):
        price = seed.get("price") or price

    photos = []
    for image in soup.find_all("img", src=True):
        src = str(image.get("src", ""))
        alt = _clean(image.get("alt"))
        if src.startswith("http") and (alt.lower().startswith("foto ") or "marketplace" in alt.lower()):
            if src not in photos:
                photos.append(src)
    videos = []
    for media in soup.find_all(["video", "source"]):
        src = str(media.get("src", ""))
        if src.startswith("http") and src not in videos:
            videos.append(src)

    lat, lng, map_url = _coordinates_from_soup(soup)

    published = None
    match = re.search(r"(Publicado\s+.+?)(?=\s+(?:Env[ií]a|Alerta|Mensaje|Guardar|Información del vendedor))", visible, re.I)
    if match:
        published = _clean(match.group(1))
    seller = None
    rating = None
    reviews = None
    joined_year = None
    seller_match = re.search(
        r"Detalles del vendedor\s+(.+?)\s+(\d[,.]\d)\s+\((\d+)\)\s+Se uni[oó] a Facebook en (\d{4})",
        visible,
        re.I,
    )
    if seller_match:
        seller, rating_raw, reviews, joined_year = seller_match.groups()
        seller = re.sub(r"[^\wÀ-ÿ .'-]+$", "", seller).strip()
        rating = float(rating_raw.replace(",", "."))

    location = seed.get("location")
    location_match = re.search(r"Publicado\s+.+?\s+en\s+(.+?),\s*AR\b", visible, re.I)
    if location_match:
        location = _clean(location_match.group(1))

    description = None
    description_match = re.search(
        r"(?:Descripción|Detalles)\s+(.+?)(?=\s+(?:Ubicación|Información del vendedor|Detalles del vendedor|Enviar mensaje))",
        visible,
        re.I,
    )
    if description_match:
        description = _clean(description_match.group(1))[:8000]

    return {
        **seed,
        "title": title or seed.get("title"),
        "location": location,
        "price": price,
        "photos": photos or ([seed["image_url"]] if seed.get("image_url") else []),
        "videos": videos,
        "image_url": (photos[0] if photos else seed.get("image_url")),
        "latitude": lat,
        "longitude": lng,
        "coordinates_accuracy": "approximate_marketplace_radius" if lat is not None else None,
        "map_url": map_url,
        "published_text": published,
        "seller_name": _clean(seller) or None,
        "seller_rating": rating,
        "seller_review_count": int(reviews) if reviews else None,
        "seller_joined_year": int(joined_year) if joined_year else None,
        "description": description,
        "visible_text_excerpt": visible[:3000],
    }


def upload_image(image_url: str | None, item_id: str, position: int = 0) -> str | None:
    if not image_url:
        return None
    try:
        request = Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=25) as response:
            content = response.read()
            content_type = response.headers.get_content_type() or "image/jpeg"
        if not content:
            return None
        extension = {"image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(content_type, "jpg")
        return upload_bytes(
            content,
            blob_name=(
                f"propiedades/facebook_marketplace_{item_id}_{position:02d}_"
                f"{datetime.now():%Y%m%d_%H%M%S}.{extension}"
            ),
            container_name="propiedadesimagenes",
            content_type=content_type,
            metadata={"fuente": "facebook_marketplace", "id_origen": item_id},
        )
    except Exception:
        return None


def standardize(item: dict[str, Any], extraction_date: str | None = None) -> dict[str, Any]:
    price = item.get("price") or {}
    location = _clean(item.get("location"))
    parts = [part.strip() for part in location.split(",") if part.strip()]
    district = parts[0] if parts else None
    raw = json.loads(json.dumps(item, default=str, ensure_ascii=False))
    searchable = _clean(f"{item.get('title', '')} {item.get('description', '')}")
    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:²|2)\b", searchable, re.I)
    bedrooms_match = re.search(r"(\d+)\s*(?:dormitorios?|habitaciones?)\b", searchable, re.I)
    bathrooms_match = re.search(r"(\d+)\s*baños?\b", searchable, re.I)
    reported_price = price.get("quality") == "reported"
    return {
        "fuente": "facebook_marketplace",
        "id_origen": str(item.get("id") or ""),
        "fecha_extraccion": extraction_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "titulo": _clean(item.get("title"))[:255] or None,
        "tipo_inmueble": infer_property_type(item.get("title", ""), item.get("description", "")),
        "tipo_operacion": operation(searchable),
        "precio_soles": price.get("amount") if reported_price and price.get("currency") == "PEN" else None,
        "precio_usd": price.get("amount") if reported_price and price.get("currency") == "USD" else None,
        "area_m2": _number(area_match.group(1)) if area_match else None,
        "dormitorios": int(bedrooms_match.group(1)) if bedrooms_match else None,
        "banos": int(bathrooms_match.group(1)) if bathrooms_match else None,
        "estacionamientos": None,
        "distrito": district,
        "provincia": "Arequipa" if classify_arequipa_location(location) is True else (parts[-1] if len(parts) > 1 else None),
        "departamento": "Arequipa" if classify_arequipa_location(location) is True else None,
        "direccion_texto": location or None,
        "latitud": item.get("latitude"),
        "longitud": item.get("longitude"),
        "descripcion": item.get("description"),
        "amenities": None,
        "url": item.get("url"),
        "imagen_url": item.get("blob_image_url") or item.get("image_url"),
        "antiguedad_anios": None,
        "agencia_agente": item.get("seller_name"),
        "datos_crudos": raw,
    }


async def scrape_marketplace(
    *,
    search_url: str = DEFAULT_SEARCH_URL,
    max_items: int = DEFAULT_MAX_ITEMS,
    start_index: int = 1,
    resume_item_ids: list[str] | None = None,
    resume_state: dict | None = None,
    discovery_only: bool = False,
    progress_callback: Callable[[dict[str, Any]], bool] | None = None,
    batch_callback: Callable[[list[dict[str, Any]]], dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    from camoufox.async_api import AsyncCamoufox
    search_url = validate_url('facebook_marketplace', search_url)
    arequipa_scope = '/marketplace/110200712339125/' in search_url or '/marketplace/arequipa/' in search_url
    radius_value = parse_qs(urlparse(search_url).query).get('radius', [None])[0]
    radius_km = number(radius_value) if radius_value is not None else AREQUIPA_RADIUS_KM
    if radius_km is None or not 0 < radius_km <= 1000:
        raise ValueError('Facebook: radio de búsqueda inválido (0 < radius <= 1000 km).')
    resume_state = resume_state or {}
    discovery = Discovery()
    completed_ids = set(resume_state.get('saved_ids') or [])
    if resume_state:
        start_index = 1  # Stable IDs, not a changing ordinal, drive recovery.

    async def visible_items(page):
        html = await page.evaluate("""() => [...document.querySelectorAll('a[href*="/marketplace/item/"]')]
            .map(anchor => anchor.outerHTML).join('')""")
        return parse_listing_html(html)

    async def emit(**payload: Any) -> bool:
        if not progress_callback:
            return True
        if await asyncio.to_thread(progress_callback, payload) is False:
            raise ScrapingInterrupted('Marketplace detenido o reemplazado')
        return True

    async def has_authenticated_session(context) -> bool:
        """Comprueba la presencia de la cookie de sesión sin leer su valor."""
        try:
            cookies = await context.cookies("https://www.facebook.com")
        except Exception:
            return False
        return any(cookie.get("name") == "c_user" for cookie in cookies)

    async def ensure_authenticated_session(context, page) -> None:
        """Garantiza una sesión antes de consumir el feed infinito.

        La vista pública de Marketplace entrega solamente uno o dos bloques
        (normalmente 24–49 anuncios). En local se abre el login y se espera a
        que el usuario lo complete una sola vez; el perfil persistente conserva
        la sesión para ejecuciones posteriores. En servidor se exige el secreto
        de cookies porque no existe una pantalla interactiva.
        """
        if await has_authenticated_session(context):
            await emit(
                percent=0,
                processed=0,
                event='session.present',
                message="Facebook Marketplace: sesión presente; verificando acceso al feed",
            )
            return

        if _running_headless():
            raise RuntimeError(
                "FACEBOOK_AUTH_REQUIRED: Marketplace necesita una sesión "
                "autenticada para recorrer más de la vista previa pública. "
                "Configure FACEBOOK_MARKETPLACE_COOKIES_JSON como secreto."
            )

        await emit(
            percent=0,
            processed=0,
            message=(
                "Facebook Marketplace: completa el inicio de sesión en la "
                "ventana Camoufox. La sesión quedará guardada para próximos "
                f"scrapeos (espera máxima: {LOGIN_WAIT_SECONDS}s)."
            ),
        )
        await page.goto(
            "https://www.facebook.com/login/",
            wait_until="domcontentloaded",
            timeout=120000,
        )
        deadline = time.monotonic() + LOGIN_WAIT_SECONDS
        while time.monotonic() < deadline:
            if await has_authenticated_session(context):
                await emit(
                    percent=0,
                    processed=0,
                    message=(
                        "Facebook Marketplace: sesión iniciada y guardada; "
                        "comenzando desplazamiento infinito"
                    ),
                )
                return
            await page.wait_for_timeout(2000)

        raise RuntimeError(
            "FACEBOOK_AUTH_REQUIRED: no se completó el inicio de sesión "
            f"dentro de {LOGIN_WAIT_SECONDS} segundos."
        )

    async def handle_auth_wall(page) -> bool:
        """Cierra el aviso preliminar o falla ante el muro definitivo.

        Facebook permite ver uno o dos lotes sin sesión, pero luego deja de
        entregar resultados. Esa vista previa nunca debe marcarse como un
        scraping completo.
        """
        try:
            validate_url('facebook_marketplace', page.url)
        except ValueError as exc:
            raise RuntimeError('FACEBOOK_SESSION_INVALID: navegación fuera de Marketplace; renovar la sesión.') from exc
        dialogs = page.locator('[role="dialog"]')
        for index in range(await dialogs.count()):
            dialog = dialogs.nth(index)
            try:
                text = _plain(await dialog.inner_text(timeout=1500))
            except Exception:
                continue
            if not any(marker in text for marker in (
                've mas en facebook', 'inicia sesion', 'iniciar sesion',
                'log in', 'sign up',
            )):
                continue

            close = dialog.get_by_role(
                'button', name=re.compile(r'^(cerrar|close)$', re.I)
            )
            if await close.count() and await close.first.is_visible():
                await close.first.click()
                await page.wait_for_timeout(600)
                return True

            if not _running_headless():
                await emit(
                    percent=1,
                    processed=0,
                    message=(
                        'Facebook Marketplace: inicia sesión en la ventana '
                        f'Camoufox; se esperará hasta {LOGIN_WAIT_SECONDS}s.'
                    ),
                )
                deadline = time.monotonic() + LOGIN_WAIT_SECONDS
                while time.monotonic() < deadline:
                    await page.wait_for_timeout(3000)
                    if not await dialog.is_visible():
                        return True

            raise RuntimeError(
                'FACEBOOK_AUTH_REQUIRED: Marketplace agotó la vista previa '
                'pública y exige una sesión autenticada para seguir cargando '
                'resultados. Configure FACEBOOK_MARKETPLACE_COOKIES_JSON o '
                'inicie sesión en el perfil Camoufox dedicado.'
            )
        return False

    async def process_candidates(
        browser,
        listing_page,
        all_candidates: list[dict[str, Any]],
        excluded_outside_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Procesa fichas desde el checkpoint sin reconstruir el feed."""
        first_position = max(1, int(start_index or 1))
        total_candidates = len(all_candidates)
        candidates = all_candidates[first_position - 1:]
        await emit(
            percent=35,
            processed=0,
            message=(
                f"Facebook Marketplace: completando {len(candidates)} fichas "
                f"desde la posición {first_position}/{total_candidates}"
            ),
        )
        detail_page = await browser.new_page()
        standardized = ScrapeRows(discovery=discovery)
        counters = {"total": 0, "nuevas": 0, "actualizadas": 0, "errores": 0}
        try:
            for position, seed in enumerate(candidates, start=first_position):
                if seed['id'] in completed_ids:
                    continue
                if not await emit(
                    percent=35 + int(
                        (position - first_position) / max(len(candidates), 1) * 63
                    ),
                    processed=counters["total"],
                    message=(
                        f"Facebook Marketplace: ficha {position}/"
                        f"{total_candidates} · {seed['id']}"
                    ),
                ):
                    break
                item = seed
                try:
                    response = await detail_page.goto(
                        validate_url('facebook_marketplace', seed["url"]),
                        wait_until="domcontentloaded",
                        timeout=90000,
                    )
                    await detail_page.wait_for_timeout(
                        DETAIL_WAIT_MS + random.randint(0, 500)
                    )
                    if response is None or response.status >= 400:
                        raise RuntimeError(f'detail.http_error: HTTP {response.status if response else None}')
                    validate_url('facebook_marketplace', detail_page.url)
                    if '/marketplace/item/' + seed['id'] + '/' not in detail_page.url:
                        raise RuntimeError('FACEBOOK_SESSION_INVALID: la ficha redirigió fuera del anuncio')
                    if await handle_auth_wall(detail_page):
                        raise RuntimeError('FACEBOOK_SESSION_INVALID: sesión requerida al abrir ficha')
                    item = parse_detail_html(await detail_page.content(), seed)
                except ScrapingInterrupted:
                    raise
                except Exception as exc:
                    discovery.details_failed += 1
                    await emit(event='detail.failed', level='error', message=str(exc),
                               property_id=seed['id'],
                               candidate_error={'id': seed['id'], 'error': str(exc)})
                    if 'FACEBOOK_' in str(exc):
                        raise  # Avoid opening every remaining detail with an expired session.
                    continue

                if arequipa_scope and not is_arequipa_item(item, radius_km):
                    excluded_outside_ids.add(item["id"])
                    await emit(
                        percent=min(
                            98,
                            35 + int((position / max(total_candidates, 1)) * 63),
                        ),
                        processed=counters["total"],
                        nuevas=counters["nuevas"],
                        actualizadas=counters["actualizadas"],
                        errores=counters["errores"],
                        checkpoint_page=position,
                        candidate_excluded=item['id'],
                        message=(
                            "Facebook Marketplace: omitida ficha fuera de "
                            f"Arequipa · {item.get('location') or item['id']}"
                        ),
                    )
                    continue
                blob_photos = []
                for image_position, image_url in enumerate(
                    (item.get("photos") or [item.get("image_url")])[
                        :MAX_IMAGES_PER_ITEM
                    ]
                ):
                    blob_url = await asyncio.to_thread(
                        upload_image, image_url, item["id"], image_position
                    )
                    if blob_url:
                        blob_photos.append(blob_url)
                    if image_url:
                        await emit(event='image.saved' if blob_url else 'image.failed',
                                   level='info' if blob_url else 'warning', property_id=item['id'],
                                   image_position=image_position,
                                   message='Marketplace: imagen almacenada' if blob_url else 'Marketplace: imagen no almacenada; URL original conservada')
                item["blob_photos"] = blob_photos
                item["blob_image_url"] = blob_photos[0] if blob_photos else None
                row = validate_row(standardize(item))
                standardized.append(row)
                if batch_callback:
                    saved = await asyncio.to_thread(batch_callback, [row])
                    counters = {
                        key: int(saved.get(key, 0) or 0) for key in counters
                    }
                    await emit(event='persistence.saved', property_id=item['id'],
                               message='Marketplace: ficha guardada', processed=counters['total'])
                else:
                    counters["total"] += 1
                if not await emit(
                    percent=min(
                        98,
                        35 + int((position / max(total_candidates, 1)) * 63),
                    ),
                    processed=counters["total"],
                    nuevas=counters["nuevas"],
                    actualizadas=counters["actualizadas"],
                    errores=counters["errores"],
                    checkpoint_page=position,
                ):
                    break
                await detail_page.wait_for_timeout(300 + random.randint(0, 500))
        finally:
            for page in (detail_page, listing_page):
                try:
                    await page.close()
                except Exception:
                    pass
        return standardized

    kwargs = await asyncio.to_thread(camoufox_kwargs,
        persistent_context=True,
        user_data_dir=PROFILE_DIR,
        timeout=int(os.environ.get('CAMOUFOX_LAUNCH_TIMEOUT', '120')) * 1000,
    )
    async with AsyncCamoufox(**kwargs) as browser:
        listing_page = await browser.new_page()
        await listing_page.set_viewport_size({"width": 1600, "height": 1000})
        if SESSION_COOKIES_JSON:
            try:
                cookies = json.loads(SESSION_COOKIES_JSON)
                if isinstance(cookies, dict):
                    cookies = cookies.get("cookies", [])
                if not isinstance(cookies, list):
                    raise ValueError("se esperaba una lista de cookies")
                await browser.add_cookies(cookies)
                await emit(
                    percent=0,
                    processed=0,
                    message="Facebook Marketplace: sesión autorizada cargada",
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "FACEBOOK_SESSION_INVALID: el secreto de sesión no es "
                    "JSON válido"
                ) from exc

        # Facebook solo deja ver 24–49 resultados sin autenticar. Validar la
        # sesión antes de abrir la búsqueda evita confundir esa vista previa
        # con el inventario completo y permite que el scroll llegue a 1000+.
        await ensure_authenticated_session(browser, listing_page)

        saved_ids = []
        seen_saved_ids: set[str] = set()
        for raw_id in resume_item_ids or []:
            item_id = str(raw_id or "").strip()
            if not item_id.isdigit() or item_id in seen_saved_ids:
                continue
            seen_saved_ids.add(item_id)
            saved_ids.append(item_id)
        if saved_ids and not resume_state:
            discovery.stop_reason = 'legacy_resume_queue'
            discovery.unique_ids = len(saved_ids)
            await emit(
                percent=35,
                processed=0,
                message=(
                    "Facebook Marketplace: cola recuperada con "
                    f"{len(saved_ids)} IDs; se omite el scroll infinito"
                ),
            )
            saved_candidates = [
                {
                    "id": item_id,
                    "url": f"https://www.facebook.com/marketplace/item/{item_id}/",
                }
                for item_id in saved_ids[:max_items]
            ]
            return await process_candidates(
                browser, listing_page, saved_candidates, set()
            )

        await emit(
            percent=1,
            processed=0,
            event='navigation.started', requested_url=search_url, radius_km=radius_km,
            message="Facebook Marketplace: abriendo búsqueda configurada",
        )
        response = await listing_page.goto(
            search_url, wait_until="domcontentloaded", timeout=120000
        )
        await listing_page.wait_for_timeout(2500)
        await handle_auth_wall(listing_page)
        if response is None or response.status >= 400:
            raise RuntimeError(f'navigation.http_error: HTTP {response.status if response else None}')
        await emit(event='navigation.loaded', requested_url=search_url, effective_url=listing_page.url,
                   http_status=response.status, message='Marketplace: búsqueda cargada')

        initial_items = await visible_items(listing_page)
        if not initial_items and not _running_headless() and os.environ.get('CAMOUFOX_HEADLESS') != '1':
            await emit(
                percent=1,
                processed=0,
                message=(
                    "Facebook Marketplace: inicia sesión en la ventana "
                    f"Camoufox; se esperará hasta {LOGIN_WAIT_SECONDS}s."
                ),
            )
            deadline = time.monotonic() + LOGIN_WAIT_SECONDS
            while time.monotonic() < deadline and not initial_items:
                await listing_page.wait_for_timeout(3000)
                initial_items = parse_listing_html(
                    await listing_page.content()
                )

        if not initial_items and _running_headless():
            page_text = _plain(await listing_page.inner_text("body"))
            auth_markers = (
                "iniciar sesion",
                "log in",
                "correo electronico o numero de telefono",
                "email or phone",
            )
            if any(marker in page_text for marker in auth_markers):
                raise RuntimeError(
                    "FACEBOOK_AUTH_REQUIRED: Azure no tiene una sesión "
                    "autorizada. Configure FACEBOOK_MARKETPLACE_COOKIES_JSON "
                    "como secreto; no se reintentará a ciegas."
                )

        excluded_outside_ids: set[str] = set()
        collected = {item['id']: item for item in resume_state.get('candidates', [])}
        pending_discoveries = []

        async def flush_discovery():
            if not pending_discoveries:
                return
            batch = [{'id': item['id'], 'raw': item, 'page': 1} for item in pending_discoveries]
            if not await emit(event='listing.discovered',
                message=f'Facebook Marketplace: {len(batch)} nuevos IDs conservados',
                candidate_batch=batch, total_unique=len(collected)):
                raise ScrapingInterrupted('Marketplace detenido durante descubrimiento')
            pending_discoveries.clear()

        def add_visible_items(items: list[dict[str, Any]]) -> int:
            added = 0
            for item in items:
                # Facebook mezcla recomendaciones de otras ciudades. Las que
                # indican explícitamente Tacna, Juliaca, Puno, etc. se eliminan
                # aquí; las ambiguas se validan con el mapa de la ficha.
                if arequipa_scope and radius_km <= AREQUIPA_RADIUS_KM and classify_arequipa_location(item.get("location")) is False:
                    excluded_outside_ids.add(item["id"])
                    continue
                if item["id"] not in collected:
                    collected[item["id"]] = item
                    pending_discoveries.append(item)
                    added += 1
            return added

        add_visible_items(initial_items)
        await flush_discovery()
        idle_rounds = 0
        scroll_round = 0
        while (
            len(collected) < max_items
            and scroll_round < MAX_SCROLL_ROUNDS
            and (
                scroll_round < MIN_SCROLL_ROUNDS
                or idle_rounds < DEFAULT_IDLE_SCROLLS
            )
        ):
            scroll_round += 1
            await handle_auth_wall(listing_page)
            before = len(collected)
            add_visible_items(await visible_items(listing_page))
            await flush_discovery()

            metrics = await listing_page.evaluate("""
                () => {
                    const anchors = [...document.querySelectorAll('a[href*="/marketplace/item/"]')];
                    const findTarget = () => {
                        let node = anchors.length ? anchors[anchors.length - 1].parentElement : null;
                        while (node && node !== document.body) {
                            const style = getComputedStyle(node);
                            if (
                                node.scrollHeight > node.clientHeight + 150
                                && /(auto|scroll)/.test(style.overflowY || '')
                            ) return node;
                            node = node.parentElement;
                        }
                        const main = document.querySelector('[role="main"]');
                        if (main) {
                            const candidates = [main, ...main.querySelectorAll('div')]
                                .filter(el => el.scrollHeight > el.clientHeight + 300)
                                .sort((a, b) => b.scrollHeight - a.scrollHeight);
                            if (candidates.length) return candidates[0];
                        }
                        return document.scrollingElement || document.documentElement;
                    };
                    const target = findTarget();
                    return {
                        y: target.scrollTop || window.scrollY || 0,
                        height: target.scrollHeight || document.documentElement.scrollHeight || 0,
                        viewport: target.clientHeight || window.innerHeight || 900,
                        target: target === document.scrollingElement ? 'document' : (
                            target.getAttribute('role') || target.tagName || 'container'
                        ),
                        visibleCards: anchors.length,
                        scrollables: [...document.querySelectorAll('div')].filter(el => {
                            const style = getComputedStyle(el);
                            return el.scrollHeight > el.clientHeight + 150
                                && /(auto|scroll)/.test(style.overflowY || '');
                        }).length
                    };
                }
            """)
            if len(collected) > before:
                idle_rounds = 0
            else:
                idle_rounds += 1

            if not await emit(
                event='scroll.progress', round=scroll_round, idle_rounds=idle_rounds,
                total_unique=len(collected), visible_cards=metrics.get('visibleCards'),
                scroll_y=metrics.get('y'), scroll_height=metrics.get('height'),
                container=metrics.get('target'), excluded=len(excluded_outside_ids),
                percent=min(35, max(2, int(len(collected) / max(max_items, 1) * 35))),
                processed=0,
                message=(
                    f"Facebook Marketplace: {len(collected)} anuncios únicos; "
                    f"scroll {scroll_round}, espera {idle_rounds}/{DEFAULT_IDLE_SCROLLS}, "
                    f"contenedor={metrics.get('target')}, visibles={metrics.get('visibleCards')}, "
                    f"scrollables={metrics.get('scrollables')}, "
                    f"fuera de Arequipa={len(excluded_outside_ids)}"
                ),
            ):
                return []

            # Facebook virtualiza la grilla: saltar directamente al final suele
            # dejar únicamente las primeras ~24 tarjetas. Un desplazamiento de
            # viewport dispara los observadores de lazy-loading gradualmente.
            moved = await listing_page.evaluate("""
                ({viewport}) => {
                    const anchors = [...document.querySelectorAll('a[href*="/marketplace/item/"]')];
                    const last = anchors[anchors.length - 1];
                    let target = last?.parentElement || null;
                    while (target && target !== document.body) {
                        const style = getComputedStyle(target);
                        if (
                            target.scrollHeight > target.clientHeight + 150
                            && /(auto|scroll)/.test(style.overflowY || '')
                        ) break;
                        target = target.parentElement;
                    }
                    if (!target || target === document.body) {
                        const main = document.querySelector('[role="main"]');
                        const candidates = main
                            ? [main, ...main.querySelectorAll('div')]
                                .filter(el => el.scrollHeight > el.clientHeight + 300)
                                .sort((a, b) => b.scrollHeight - a.scrollHeight)
                            : [];
                        target = candidates[0] || document.scrollingElement || document.documentElement;
                    }
                    const before = target.scrollTop;
                    last?.scrollIntoView({block: 'end', behavior: 'instant'});
                    target.scrollBy({
                        top: Math.max(650, viewport * 0.82),
                        left: 0,
                        behavior: 'instant'
                    });
                    return target.scrollTop !== before;
                }
            """, {"viewport": int(metrics.get("viewport", 900) or 900)})

            # Fallback de entrada real: ayuda cuando React intercepta el wheel
            # sobre la grilla y el contenedor no expone overflow CSS estable.
            if not moved:
                await listing_page.mouse.move(1200, 850)
            wheel_distance = max(700, int(metrics.get("viewport", 900) or 900))
            for _ in range(max(1, SCROLL_WHEEL_BURST)):
                await listing_page.mouse.wheel(0, wheel_distance)
                await listing_page.wait_for_timeout(180 + random.randint(0, 120))

            # Último recurso para las variantes donde Facebook reparte el
            # desplazamiento entre varios contenedores React. Se desplazan
            # simultáneamente únicamente los elementos que realmente tienen
            # overflow vertical y la última tarjeta se vuelve a poner en vista.
            await listing_page.evaluate("""
                () => {
                    const scrollables = [...document.querySelectorAll('div')].filter(el => {
                        const style = getComputedStyle(el);
                        return el.scrollHeight > el.clientHeight + 150
                            && /(auto|scroll)/.test(style.overflowY || '');
                    });
                    for (const el of scrollables) {
                        el.scrollTop += Math.max(600, el.clientHeight * 0.9);
                        el.dispatchEvent(new Event('scroll', {bubbles: true}));
                    }
                    const anchors = document.querySelectorAll('a[href*="/marketplace/item/"]');
                    anchors[anchors.length - 1]?.scrollIntoView({block: 'end', behavior: 'instant'});
                    window.scrollBy(0, Math.max(700, window.innerHeight * 0.9));
                }
            """)
            await listing_page.keyboard.press("PageDown")

            # Muestrear varias veces: las tarjetas aparecen después del fetch y
            # Facebook puede retirar las anteriores del DOM. `collected`
            # conserva todos los IDs vistos durante la sesión.
            samples = 4 if idle_rounds else 2
            for _ in range(samples):
                await listing_page.wait_for_timeout(
                    max(500, SCROLL_WAIT_MS // samples) + random.randint(0, 250)
                )
                sample_before = len(collected)
                add_visible_items(await visible_items(listing_page))
                if len(collected) > sample_before:
                    idle_rounds = 0
                await flush_discovery()
                await handle_auth_wall(listing_page)

            # En algunos diseños el feed ofrece un botón explícito además del
            # infinite scroll. Solo se pulsa cuando su texto indica resultados.
            await listing_page.evaluate("""
                () => {
                    const pattern = /^(ver|mostrar|cargar|see|show|load)\\s+(m[aá]s\\s+)?(resultados?|anuncios?|listings?|results?)$/i;
                    const candidates = [...document.querySelectorAll('[role="button"], button')];
                    const target = candidates.find(el => pattern.test((el.innerText || '').trim()));
                    if (target) target.click();
                    return Boolean(target);
                }
            """)

        await flush_discovery()
        discovery.pages = scroll_round
        discovery.unique_ids = len(collected)
        discovery.final_url = listing_page.url
        discovery.stop_reason = ('max_items' if len(collected) >= max_items else
            'max_scroll_rounds' if scroll_round >= MAX_SCROLL_ROUNDS else 'stalled')
        # Inactivity alone does not prove that a personalized feed is exhaustive.
        discovery.complete = False
        await emit(event='discovery.finished', level='warning', discovery=discovery.as_dict(),
                   message=f'Facebook Marketplace: {discovery.stop_reason}; {len(collected)} IDs descubiertos')

        if not collected:
            page_text = _plain(await listing_page.inner_text("body"))
            if "iniciar sesion" in page_text or "log in" in page_text:
                raise RuntimeError(
                    "Facebook Marketplace requiere iniciar sesión en el perfil Camoufox dedicado."
                )
            raise RuntimeError("Facebook Marketplace no devolvió tarjetas visibles.")

        candidates = list(collected.values())[:max_items]
        if discovery_only:
            return ScrapeRows([standardize(item) for item in candidates], discovery=discovery)
        if not await emit(
            percent=35,
            processed=0,
            resume_item_ids=[item["id"] for item in candidates],
            message=(
                "Facebook Marketplace: cola de reanudación guardada con "
                f"{len(candidates)} IDs"
            ),
        ):
            return []
        return await process_candidates(
            browser, listing_page, candidates, excluded_outside_ids
        )


def run_scraper(**kwargs: Any) -> list[dict[str, Any]]:
    try:
        return asyncio.run(asyncio.wait_for(scrape_marketplace(**kwargs), timeout=TOTAL_TIMEOUT))
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"Facebook Marketplace superó el timeout total de {TOTAL_TIMEOUT}s."
        ) from exc
