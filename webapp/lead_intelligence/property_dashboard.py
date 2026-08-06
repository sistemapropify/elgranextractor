from __future__ import annotations

from collections import defaultdict

from django.db import connections
from django.utils import timezone

from intelligence.models import IntelligenceCollection, IntelligenceDocument

from .contextual_analysis import conversation_hash
from .conversation_analysis import analyze_chat_history
from .services import _apply_contextual_assessment, _assessment_map, _dict_rows
from .visit_resolution import resolve_visits_for_leads


PROPERTY_COLLECTION_NAME = "propiedadespropify"
PORTFOLIO_FIELD = "is_propify_portfolio"


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _portfolio_value(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "si", "sí"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _text(value, fallback="Sin dato"):
    value = str(value or "").strip()
    return value or fallback


def _price_display(fields):
    price = fields.get("price")
    if price in (None, ""):
        return "Precio no registrado"
    try:
        numeric = float(price)
    except (TypeError, ValueError):
        return str(price)
    currency = str(fields.get("currency_name") or "").lower()
    symbol = (
        "S/"
        if "sol" in currency
        else "US$" if "dolar" in currency or "dólar" in currency else ""
    )
    return f"{symbol} {numeric:,.0f}".strip()


def _property_card(document):
    fields = document.field_values or {}
    property_id = _integer(fields.get("id") or document.source_id)
    if property_id is None:
        return None
    portfolio = _portfolio_value(fields.get(PORTFOLIO_FIELD))
    image_url = fields.get("media_preview_url") or fields.get("media_drive_url")
    return {
        "property_id": property_id,
        "source_id": document.source_id,
        "code": _text(fields.get("code"), f"Propiedad #{property_id}"),
        "title": _text(fields.get("title"), "Propiedad sin título"),
        "image_url": str(image_url or "").strip(),
        "portfolio": portfolio,
        "portfolio_key": "own" if portfolio is True else "external" if portfolio is False else "unknown",
        "portfolio_label": "Propify" if portfolio is True else "Agente externo" if portfolio is False else "Sin clasificar",
        "district": _text(fields.get("district_name")),
        "property_type": _text(fields.get("property_type_name")),
        "operation_type": _text(fields.get("operation_type_name")),
        "status": _text(fields.get("property_status_name")),
        "responsible": _text(fields.get("responsible_name"), "Sin responsable"),
        "price_display": _price_display(fields),
        "lead_count": 0,
        "contacted": 0,
        "bidirectional": 0,
        "qualified": 0,
        "visit_intent": 0,
        "visit_registered": 0,
        "unattended": 0,
    }


def _filter_cards(cards, filters):
    result = []
    query = filters["query"].casefold()
    for card in cards:
        if filters["portfolio"] != "all" and card["portfolio_key"] != filters["portfolio"]:
            continue
        if filters["district"] and card["district"] != filters["district"]:
            continue
        if filters["property_type"] and card["property_type"] != filters["property_type"]:
            continue
        if filters["operation"] and card["operation_type"] != filters["operation"]:
            continue
        if filters["status"] and card["status"] != filters["status"]:
            continue
        if query and query not in f"{card['code']} {card['title']} {card['responsible']}".casefold():
            continue
        result.append(card)
    return result


def aggregate_property_metrics(cards, analyzed_rows, visit_pairs):
    cards_by_id = {card["property_id"]: card for card in cards}
    seen_pairs = set()
    for row in analyzed_rows:
        property_id = _integer(row.get("property_id"))
        lead_id = _integer(row.get("id") or row.get("lead_id"))
        pair = (property_id, lead_id)
        card = cards_by_id.get(property_id)
        if card is None or lead_id is None or pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        card["lead_count"] += 1
        for key in ("contacted", "bidirectional", "qualified", "visit_intent", "unattended"):
            card[key] += int(bool(row.get(key)))
        card["visit_registered"] += int(pair in visit_pairs)

    for card in cards:
        total = card["lead_count"]
        for key in ("contacted", "bidirectional", "qualified", "visit_intent", "visit_registered", "unattended"):
            card[f"{key}_pct"] = round(card[key] / total * 100, 1) if total else 0
    return cards


def _load_lead_rows(property_ids, date_from, date_to):
    if not property_ids:
        return []
    placeholders = ", ".join(["%s"] * len(property_ids))
    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT
                lp.property_id,
                l.id,
                l.chat_history,
                COALESCE(l.date_entry, l.created_at) AS entered_at
            FROM dbo.lead_properties lp
            INNER JOIN dbo.lead l ON l.id = lp.lead_id
            WHERE lp.property_id IN ({placeholders})
              AND CAST(
                    SWITCHOFFSET(COALESCE(l.date_entry, l.created_at), '-05:00')
                    AS date
                  ) BETWEEN %s AND %s
            """,
            [*property_ids, date_from, date_to],
        )
        return _dict_rows(cursor)


def _load_visit_pairs(property_ids, lead_ids):
    if not property_ids or not lead_ids:
        return set()
    selected_properties = {int(property_id) for property_id in property_ids}
    return {
        (int(row["event_property_id"]), int(row["resolved_lead_id"]))
        for row in resolve_visits_for_leads(lead_ids)
        if row.get("event_property_id") is not None
        and int(row["event_property_id"]) in selected_properties
    }


def _analyze_rows(rows):
    assessments = _assessment_map(rows)
    analyzed = []
    for row in rows:
        analysis = _apply_contextual_assessment(
            analyze_chat_history(row.get("chat_history")),
            assessments.get((row["id"], conversation_hash(row.get("chat_history")))),
        )
        analyzed.append({**row, **analysis})
    return analyzed


def _summary(cards, analyzed_rows):
    unique_leads = {row["id"] for row in analyzed_rows}
    own = [card for card in cards if card["portfolio"] is True]
    external = [card for card in cards if card["portfolio"] is False]
    return {
        "properties": len(cards),
        "own_properties": len(own),
        "external_properties": len(external),
        "unclassified_properties": sum(card["portfolio"] is None for card in cards),
        "unique_leads": len(unique_leads),
        "property_lead_links": sum(card["lead_count"] for card in cards),
        "properties_without_leads": sum(card["lead_count"] == 0 for card in cards),
        "properties_with_unattended": sum(card["unattended"] > 0 for card in cards),
    }


def _portfolio_comparison(cards):
    rows = []
    for key, label in ((True, "Propify"), (False, "Agentes externos")):
        group = [card for card in cards if card["portfolio"] is key]
        leads = sum(card["lead_count"] for card in group)
        qualified = sum(card["qualified"] for card in group)
        visits = sum(card["visit_registered"] for card in group)
        rows.append({
            "label": label,
            "properties": len(group),
            "leads": leads,
            "qualified": qualified,
            "visits": visits,
            "qualification_pct": round(qualified / leads * 100, 1) if leads else 0,
            "visit_pct": round(visits / leads * 100, 1) if leads else 0,
        })
    return rows


def get_property_dashboard(date_from, date_to, raw_filters):
    collection = (
        IntelligenceCollection.objects.using("default")
        .filter(name=PROPERTY_COLLECTION_NAME)
        .first()
    )
    documents = [] if collection is None else list(
        IntelligenceDocument.objects.using("default")
        .filter(collection_id=collection.id)
        .only("source_id", "field_values")
    )
    all_cards = [card for card in (_property_card(document) for document in documents) if card]
    options = {
        "districts": sorted({card["district"] for card in all_cards if card["district"] != "Sin dato"}),
        "property_types": sorted({card["property_type"] for card in all_cards if card["property_type"] != "Sin dato"}),
        "operations": sorted({card["operation_type"] for card in all_cards if card["operation_type"] != "Sin dato"}),
        "statuses": sorted({card["status"] for card in all_cards if card["status"] != "Sin dato"}),
    }
    filters = {
        "portfolio": raw_filters.get("portfolio") if raw_filters.get("portfolio") in {"all", "own", "external", "unknown"} else "all",
        "district": str(raw_filters.get("district") or "").strip(),
        "property_type": str(raw_filters.get("property_type") or "").strip(),
        "operation": str(raw_filters.get("operation") or "").strip(),
        "status": str(raw_filters.get("status") or "").strip(),
        "query": str(raw_filters.get("q") or "").strip(),
        "sort": str(raw_filters.get("sort") or "leads_desc").strip(),
    }
    cards = _filter_cards(all_cards, filters)
    property_ids = [card["property_id"] for card in cards]
    lead_rows = _load_lead_rows(property_ids, date_from, date_to)
    analyzed_rows = _analyze_rows(lead_rows)
    lead_ids = sorted({row["id"] for row in lead_rows})
    visit_pairs = _load_visit_pairs(property_ids, lead_ids)
    aggregate_property_metrics(cards, analyzed_rows, visit_pairs)

    sorters = {
        "leads_desc": lambda card: (-card["lead_count"], card["code"]),
        "qualified_desc": lambda card: (-card["qualified"], -card["lead_count"], card["code"]),
        "visits_desc": lambda card: (-card["visit_registered"], -card["lead_count"], card["code"]),
        "conversion_desc": lambda card: (-card["qualified_pct"], -card["lead_count"], card["code"]),
        "unattended_desc": lambda card: (-card["unattended"], -card["lead_count"], card["code"]),
        "code": lambda card: card["code"],
    }
    cards.sort(key=sorters.get(filters["sort"], sorters["leads_desc"]))
    return {
        "generated_at": timezone.now(),
        "date_from": date_from,
        "date_to": date_to,
        "filters": filters,
        "filter_options": options,
        "cards": cards,
        "summary": _summary(cards, analyzed_rows),
        "portfolio_comparison": _portfolio_comparison(cards),
        "collection_found": collection is not None,
        "portfolio_field": PORTFOLIO_FIELD,
    }
