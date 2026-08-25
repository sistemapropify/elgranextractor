"""Extraccion publica de Facebook Marketplace mediante Camoufox.

No usa endpoints GraphQL privados ni intenta revelar ``[hidden information]``.
Los selectores se apoyan en la URL estable ``/marketplace/item/<id>`` y en
contenido visible para resistir cambios de clases CSS generadas por Facebook.
"""

from __future__ import annotations

import asyncio
import json
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


DEFAULT_SEARCH_URL = os.environ.get(
    "FACEBOOK_MARKETPLACE_SEARCH_URL",
    "https://www.facebook.com/marketplace/arequipa/search/"
    "?category_id=1270772586445798&query=Viviendas%20en%20venta",
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
LOGIN_WAIT_SECONDS = int(os.environ.get("FACEBOOK_MARKETPLACE_LOGIN_WAIT_SECONDS", "180"))
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
        "tipo_operacion": "Alquiler" if "alquil" in _plain(item.get("title", "")) else "Venta",
        "precio_soles": price.get("amount") if reported_price and price.get("currency") == "PEN" else None,
        "precio_usd": price.get("amount") if reported_price and price.get("currency") == "USD" else None,
        "area_m2": _number(area_match.group(1)) if area_match else None,
        "dormitorios": int(bedrooms_match.group(1)) if bedrooms_match else None,
        "banos": int(bathrooms_match.group(1)) if bathrooms_match else None,
        "estacionamientos": None,
        "distrito": district,
        "provincia": "Arequipa",
        "departamento": "Arequipa",
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
    progress_callback: Callable[[dict[str, Any]], bool] | None = None,
    batch_callback: Callable[[list[dict[str, Any]]], dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    from camoufox.async_api import AsyncCamoufox

    async def emit(**payload: Any) -> bool:
        if not progress_callback:
            return True
        return bool(await asyncio.to_thread(progress_callback, payload))

    async def handle_auth_wall(page) -> bool:
        """Cierra el aviso preliminar o falla ante el muro definitivo.

        Facebook permite ver uno o dos lotes sin sesión, pero luego deja de
        entregar resultados. Esa vista previa nunca debe marcarse como un
        scraping completo.
        """
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

            if not is_headless_server():
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

    kwargs = camoufox_kwargs(
        persistent_context=True,
        user_data_dir=PROFILE_DIR,
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

        await emit(
            percent=1,
            processed=0,
            message="Facebook Marketplace: abriendo búsqueda en Arequipa",
        )
        await listing_page.goto(
            search_url, wait_until="domcontentloaded", timeout=120000
        )
        await listing_page.wait_for_timeout(2500)
        await handle_auth_wall(listing_page)

        initial_items = parse_listing_html(await listing_page.content())
        if not initial_items and not is_headless_server():
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

        if not initial_items and is_headless_server():
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

        collected: dict[str, dict[str, Any]] = {
            item["id"]: item for item in initial_items
        }
        idle_rounds = 0
        scroll_round = 0
        previous_height = 0
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
            for item in parse_listing_html(await listing_page.content()):
                collected.setdefault(item["id"], item)

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
            height_grew = int(metrics.get("height", 0) or 0) > previous_height
            previous_height = max(previous_height, int(metrics.get("height", 0) or 0))
            if len(collected) > before or height_grew:
                idle_rounds = 0
            else:
                idle_rounds += 1

            if not await emit(
                percent=min(35, max(2, int(len(collected) / max(max_items, 1) * 35))),
                processed=0,
                message=(
                    f"Facebook Marketplace: {len(collected)} anuncios únicos; "
                    f"scroll {scroll_round}, espera {idle_rounds}/{DEFAULT_IDLE_SCROLLS}, "
                    f"contenedor={metrics.get('target')}, visibles={metrics.get('visibleCards')}, "
                    f"scrollables={metrics.get('scrollables')}"
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
                for item in parse_listing_html(await listing_page.content()):
                    collected.setdefault(item["id"], item)
                if len(collected) > sample_before:
                    idle_rounds = 0
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

        if (
            len(collected) <= len(initial_items)
            and len(initial_items) >= 20
            and max_items > len(initial_items)
        ):
            raise RuntimeError(
                "Facebook Marketplace mantuvo el primer bloque de "
                f"{len(initial_items)} anuncios después de {scroll_round} scrolls; "
                "el listado no avanzó y no se marcará falsamente como completado."
            )

        if not collected:
            page_text = _plain(await listing_page.inner_text("body"))
            if "iniciar sesion" in page_text or "log in" in page_text:
                raise RuntimeError(
                    "Facebook Marketplace requiere iniciar sesión en el perfil Camoufox dedicado."
                )
            raise RuntimeError("Facebook Marketplace no devolvió tarjetas visibles.")

        candidates = list(collected.values())[:max_items]
        candidates = candidates[max(0, int(start_index or 1) - 1):]
        await emit(percent=35, processed=0, message=f"Facebook Marketplace: completando {len(candidates)} fichas")
        detail_page = await browser.new_page()
        standardized: list[dict[str, Any]] = []
        counters = {"total": 0, "nuevas": 0, "actualizadas": 0, "errores": 0}
        for position, seed in enumerate(candidates, start=max(1, int(start_index or 1))):
            if not await emit(
                percent=35 + int((position - max(1, int(start_index or 1))) / max(len(candidates), 1) * 63),
                processed=counters["total"],
                message=f"Facebook Marketplace: ficha {position}/{len(collected)} · {seed['id']}",
            ):
                break
            item = seed
            try:
                await detail_page.goto(seed["url"], wait_until="domcontentloaded", timeout=90000)
                await detail_page.wait_for_timeout(DETAIL_WAIT_MS + random.randint(0, 500))
                item = parse_detail_html(await detail_page.content(), seed)
            except Exception as exc:
                item = {**seed, "detail_error": str(exc)[:500]}
            blob_photos = []
            for image_position, image_url in enumerate(
                (item.get("photos") or [item.get("image_url")])[:MAX_IMAGES_PER_ITEM]
            ):
                blob_url = await asyncio.to_thread(
                    upload_image, image_url, item["id"], image_position
                )
                if blob_url:
                    blob_photos.append(blob_url)
            item["blob_photos"] = blob_photos
            item["blob_image_url"] = blob_photos[0] if blob_photos else None
            row = standardize(item)
            standardized.append(row)
            if batch_callback:
                saved = await asyncio.to_thread(batch_callback, [row])
                counters = {key: int(saved.get(key, 0) or 0) for key in counters}
            else:
                counters["total"] += 1
            if not await emit(
                percent=min(98, 35 + int((position / max(len(collected), 1)) * 63)),
                processed=counters["total"],
                nuevas=counters["nuevas"],
                actualizadas=counters["actualizadas"],
                errores=counters["errores"],
                checkpoint_page=position,
            ):
                break
            await detail_page.wait_for_timeout(300 + random.randint(0, 500))
        await detail_page.close()
        await listing_page.close()
        return standardized


def run_scraper(**kwargs: Any) -> list[dict[str, Any]]:
    try:
        return asyncio.run(asyncio.wait_for(scrape_marketplace(**kwargs), timeout=TOTAL_TIMEOUT))
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"Facebook Marketplace superó el timeout total de {TOTAL_TIMEOUT}s."
        ) from exc
