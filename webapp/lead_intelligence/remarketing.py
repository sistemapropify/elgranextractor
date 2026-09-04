"""Read-only analytics for the n8n remarketing follow-up template."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import median

from django.db import connections
from django.utils import timezone

from .attention_quality import duration_label
from .contextual_analysis import ANALYSIS_VERSION, conversation_hash
from .conversation_analysis import LIMA_TIMEZONE, _timestamp, normalize_text
from .models import LeadConversationAssessment


REMARKETING_TEMPLATE_CODE = "hola_de_nuevo_propiedad"
REMARKETING_TEMPLATE_LABEL = "Intento 1 · Hola de nuevo"
REMARKETING_ATTEMPT = 1
REMARKETING_SQL_HINT = "%Hola de nuevo%te sigue interesando la propiedad%"
REMARKETING_SIGNATURE = (
    "hola de nuevo si te sigue interesando la propiedad puedo coordinarte "
    "una visita"
)
OUTBOUND_SENDERS = {"agent", "bot"}
OUTCOME_OPTIONS = (
    ("all", "Todos los lanzamientos"),
    ("responded", "Con respuesta"),
    ("no_response", "Sin respuesta"),
    ("qualified", "Calificados por IA"),
    ("visit", "Con intención de visita"),
)


# ─────────────────────────────────────────────────────────────────────────
# Plantillas de mensaje: autorizadas desde la BD (PlantillaMensaje).
# El dashboard analiza TODAS las plantillas activas, no solo una fija.
# ─────────────────────────────────────────────────────────────────────────
def _plantillas_activas():
    """Plantillas autorizadas (activa=True) desde la BD.

    Si la tabla aún está vacía o no existe, se usa como fallback la plantilla
    histórica de remarketing (constantes REMARKETING_*).
    """
    from .models import PlantillaMensaje

    try:
        rows = list(
            PlantillaMensaje.objects.using("default")
            .filter(activa=True)
            .order_by("orden", "id")
            .values(
                "codigo",
                "titulo",
                "orden",
                "frase_condicion",
                "regex_condicion",
                "sql_hint",
            )
        )
    except Exception:
        rows = []
    if rows:
        return rows
    return [
        {
            "codigo": REMARKETING_TEMPLATE_CODE,
            "titulo": REMARKETING_TEMPLATE_LABEL,
            "orden": REMARKETING_ATTEMPT,
            "frase_condicion": REMARKETING_SIGNATURE,
            "regex_condicion": "",
            "sql_hint": REMARKETING_SQL_HINT,
        }
    ]


def matchea_plantilla(plantilla, texto_normalizado):
    """True si un mensaje normalizado cumple la condición de la plantilla."""
    frase = _plain_text(plantilla.get("frase_condicion") or "")
    if frase and frase in texto_normalizado:
        return True
    regex = (plantilla.get("regex_condicion") or "").strip()
    if regex:
        try:
            if re.search(regex, texto_normalizado):
                return True
        except re.error:
            pass
    return False


def detectar_plantillas(texto):
    """Devuelve la lista de plantillas activas que matchean un mensaje."""
    texto_normalizado = _plain_text(texto or "")
    if not texto_normalizado:
        return []
    return [
        plantilla
        for plantilla in _plantillas_activas()
        if matchea_plantilla(plantilla, texto_normalizado)
    ]


def _dict_rows(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _plain_text(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def is_remarketing_message(text):
    """True si el mensaje pertenece a alguna plantilla activa autorizada."""

    return bool(detectar_plantillas(text))


def _message_text(message):
    for key in ("text", "content", "body", "caption"):
        value = message.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _raw_timeline(raw_history):
    if isinstance(raw_history, str):
        try:
            payload = json.loads(raw_history)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    elif isinstance(raw_history, list):
        payload = raw_history
    else:
        return []
    if not isinstance(payload, list):
        return []

    timeline = []
    seen = set()
    for position, raw in enumerate(payload):
        if not isinstance(raw, dict):
            continue
        sender = normalize_text(raw.get("sender"))
        timestamp = _timestamp(raw.get("timestamp"))
        text = _message_text(raw)
        if sender not in {"lead", "agent", "bot"} or timestamp is None or not text:
            continue
        message_id = str(raw.get("id") or "").strip()
        dedupe_key = (
            ("id", message_id)
            if message_id
            else ("content", sender, text, timestamp.isoformat())
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        timeline.append(
            {
                "position": position,
                "message_id": message_id,
                "sender": sender,
                "sender_name": str(raw.get("sender_name") or "").strip(),
                "timestamp": timestamp,
                "text": text,
            }
        )
    timeline.sort(key=lambda item: (item["timestamp"], item["position"]))
    return timeline


def detect_remarketing_launches(raw_history):
    """Devuelve lanzamientos de TODAS las plantillas activas autorizadas.

    Cada mensaje saliente se atribuye a cada plantilla activa que matchea.
    La respuesta de un lead se acredita a un lanzamiento solo si ocurre antes
    del siguiente lanzamiento de la MISMA plantilla (evita acreditar varias
    respuestas a reintentos de una misma plantilla).
    """

    timeline = _raw_timeline(raw_history)
    if not timeline:
        return []

    # Normalizar y detectar plantilla una sola vez por mensaje saliente.
    por_mensaje = []
    for message in timeline:
        if message["sender"] in OUTBOUND_SENDERS:
            por_mensaje.append((message, detectar_plantillas(message["text"])))
        else:
            por_mensaje.append((message, []))

    seq_por_plantilla = defaultdict(int)
    launches = []
    for position, (message, matcheadas) in enumerate(por_mensaje):
        if message["sender"] not in OUTBOUND_SENDERS or not matcheadas:
            continue
        for plantilla in matcheadas:
            codigo = plantilla["codigo"]
            seq_por_plantilla[codigo] += 1
            plantilla_seq = seq_por_plantilla[codigo]

            # Siguiente lanzamiento de la MISMA plantilla delimita la ventana.
            ventana_fin = len(timeline)
            for siguiente_position in range(position + 1, len(por_mensaje)):
                otro_mensaje, otras = por_mensaje[siguiente_position]
                if otro_mensaje["sender"] in OUTBOUND_SENDERS and any(
                    otra["codigo"] == codigo for otra in otras
                ):
                    ventana_fin = siguiente_position
                    break

            response = next(
                (
                    candidate
                    for candidate in timeline[position + 1 : ventana_fin]
                    if candidate["sender"] == "lead"
                ),
                None,
            )
            previous = timeline[position - 1] if position else None
            launches.append(
                {
                    **message,
                    "plantilla_codigo": codigo,
                    "plantilla_titulo": plantilla["titulo"],
                    "plantilla_orden": int(plantilla.get("orden") or 1),
                    "launch_sequence_for_plantilla": plantilla_seq,
                    "response_at": response["timestamp"] if response else None,
                    "response_text": response["text"] if response else "",
                    "response_seconds": (
                        int((response["timestamp"] - message["timestamp"]).total_seconds())
                        if response
                        else None
                    ),
                    "previous_sender": previous["sender"] if previous else None,
                    "previous_at": previous["timestamp"] if previous else None,
                    "delay_from_previous_seconds": (
                        int((message["timestamp"] - previous["timestamp"]).total_seconds())
                        if previous
                        else None
                    ),
                }
            )

    launches.sort(key=lambda item: (item["timestamp"], item["position"]))
    return launches


def _assessment_map(rows):
    keys = {
        (int(row["id"]), conversation_hash(row.get("chat_history")))
        for row in rows
    }
    if not keys:
        return {}
    assessments = (
        LeadConversationAssessment.objects.using("default")
        .filter(
            source_lead_id__in={lead_id for lead_id, _ in keys},
            analysis_version=ANALYSIS_VERSION,
        )
        .order_by("-analyzed_at")
    )
    result = {}
    for assessment in assessments:
        key = (int(assessment.source_lead_id), assessment.history_hash)
        if key in keys and key not in result:
            result[key] = assessment
    return result


def _evidence_times(evidence):
    values = []
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        parsed = _timestamp(item.get("timestamp"))
        if parsed is not None:
            values.append(parsed)
    return values


def _after_launch(assessment, field_name, launch_at, next_launch_at=None):
    if assessment is None or getattr(assessment, f"{field_name}_status") != "confirmed":
        return False
    for timestamp in _evidence_times(getattr(assessment, f"{field_name}_evidence")):
        if timestamp >= launch_at and (
            next_launch_at is None or timestamp < next_launch_at
        ):
            return True
    return False


def _percent(numerator, denominator):
    return round(numerator / denominator * 100, 1) if denominator else 0


def _median_label(values):
    values = [value for value in values if value is not None and value >= 0]
    return duration_label(median(values)) if values else "—"


# ─────────────────────────────────────────────────────────────────────────
# Soporte para N plantillas independientes + granularidad temporal
# (día / semana / mes) para ver cómo evolucionó CADA plantilla.
# ─────────────────────────────────────────────────────────────────────────
GRANULARIDAD_OPTIONS = (
    ("dia", "Día"),
    ("semana", "Semana"),
    ("mes", "Mes"),
)
_PLANTILLA_COLORS = [
    "#58a6ff", "#3fb950", "#f0883e", "#d2a8ff",
    "#ffa198", "#7ee787", "#79c0ff", "#e3b341",
]


def _etiqueta_visual(titulo):
    """Quita prefijos 'Intento N · ' del título para mostrar cada plantilla
    como independiente (no como el 'intento 2' de otra)."""
    if not titulo:
        return titulo
    limpio = re.sub(
        r"^\s*intento\s+\d+\s*[·:\-]\s*", "", str(titulo), flags=re.IGNORECASE
    ).strip()
    return limpio or str(titulo)


def _color_plantilla(idx):
    return _PLANTILLA_COLORS[idx % len(_PLANTILLA_COLORS)]


def _bucket_key(fecha, granularidad):
    if granularidad == "mes":
        return fecha.replace(day=1)
    if granularidad == "semana":
        return fecha - timedelta(days=fecha.weekday())
    return fecha


def _bucket_label(key, granularidad, siguiente=None):
    if granularidad == "mes":
        return key.strftime("%b %Y")
    if granularidad == "semana":
        fin = (siguiente or (key + timedelta(days=7))) - timedelta(days=1)
        return f"{key.strftime('%d %b')} – {fin.strftime('%d %b')}"
    return key.strftime("%d %b %y")


def _timeline_rows(events, date_from, date_to, granularidad, plantillas):
    """Genera buckets (día/semana/mes) con el detalle por plantilla.

    Cada fila trae totales y el desglose ``plants`` de TODAS las plantillas
    activas (dinámico: 2 hoy, 4 mañana) para poder compararlas en el tiempo.
    """
    granularidad = granularidad if granularidad in {"dia", "semana", "mes"} else "dia"
    order = {}
    it = date_from
    while it <= date_to:
        b = _bucket_key(it, granularidad)
        order.setdefault(b.isoformat(), b)
        it += timedelta(days=1)
    buckets = {iso: _Bucket(day) for iso, day in order.items()}
    for ev in events:
        b = _bucket_key(ev["launch_date"], granularidad)
        bucket = buckets.get(b.isoformat())
        if bucket is None:
            continue
        plant = bucket.por_plantilla[ev["plantilla_codigo"]]
        plant["sent"] += 1
        plant["responded"] += int(ev["responded"])
        plant["repeated"] += int(ev.get("duplicate_first_attempt", False))

    sorted_keys = sorted(buckets.keys())
    color_por_codigo = {
        pl["codigo"]: _color_plantilla(idx) for idx, pl in enumerate(plantillas)
    }
    rows = []
    for pos, iso in enumerate(sorted_keys):
        bucket = buckets[iso]
        siguiente = buckets.get(sorted_keys[pos + 1]) if pos + 1 < len(sorted_keys) else None
        plants = [
            {
                "codigo": pl["codigo"],
                "titulo": _etiqueta_visual(pl["titulo"]),
                "color": color_por_codigo.get(pl["codigo"], "#58a6ff"),
                "sent": bucket.por_plantilla.get(pl["codigo"], {}).get("sent", 0),
                "responded": bucket.por_plantilla.get(pl["codigo"], {}).get("responded", 0),
                "repeated": bucket.por_plantilla.get(pl["codigo"], {}).get("repeated", 0),
            }
            for pl in plantillas
        ]
        total_sent = sum(p["sent"] for p in plants)
        total_responded = sum(p["responded"] for p in plants)
        total_repeated = sum(p["repeated"] for p in plants)
        rows.append(
            {
                "key": bucket.day.isoformat(),
                "label": _bucket_label(bucket.day, granularidad, siguiente.day if siguiente else None),
                "sent": total_sent,
                "responded": total_responded,
                "repeated": total_repeated,
                "no_response": total_sent - total_responded,
                "response_pct": _percent(total_responded, total_sent),
                "plants": plants,
            }
        )
    peak = max((row["sent"] for row in rows), default=0)
    for row in rows:
        row["sent_bar_pct"] = _percent(row["sent"], peak)
        row["responded_bar_pct"] = _percent(row["responded"], peak)
    return rows


class _Bucket:
    """Agregación de un bucket temporal por plantilla."""

    def __init__(self, day):
        self.day = day
        self.por_plantilla = defaultdict(
            lambda: {"sent": 0, "responded": 0, "repeated": 0}
        )


def _lead_rows():
    """Leads cuyo chat_history contiene el hint de CUALQUIER plantilla activa."""
    plantillas = _plantillas_activas()
    hints = [
        hint
        for hint in ((plantilla.get("sql_hint") or "").strip() for plantilla in plantillas)
        if hint
    ]
    if not hints:
        hints = [REMARKETING_SQL_HINT]
    clause = " OR ".join("l.chat_history LIKE %s" for _ in hints)
    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                l.id,
                l.chat_history,
                l.id_chatwoot,
                l.source,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(CONCAT(c.first_name, ' ', c.last_name))), ''),
                    c.business_name,
                    CONCAT('Lead #', l.id)
                ) AS display_name,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(CONCAT(u.first_name, ' ', u.last_name))), ''),
                    u.username,
                    'Sin asignar'
                ) AS agent_name,
                l.assigned_to_id AS agent_id,
                COALESCE(ls.name, 'Sin estado') AS status_name,
                COALESCE(mc.name, 'Sin campaña') AS campaign_name
            FROM dbo.lead l
            LEFT JOIN dbo.contact c ON c.id = l.contact_id
            LEFT JOIN dbo.[user] u ON u.id = l.assigned_to_id
            LEFT JOIN dbo.lead_status ls ON ls.id = l.lead_status_id
            LEFT JOIN dbo.meta_campaign mc ON mc.id = l.meta_campaign_ref_id
            WHERE {clause}
            """,
            hints,
        )
        return _dict_rows(cursor)


def _daily_rows(events, date_from, date_to):
    grouped = defaultdict(Counter)
    for event in events:
        day = event["launch_date"]
        grouped[day]["sent"] += 1
        grouped[day]["responded"] += int(event["responded"])
        grouped[day]["qualified"] += int(event["qualified_after"])
        grouped[day]["visit"] += int(event["visit_after"])
        grouped[day]["repeated"] += int(event["duplicate_first_attempt"])
    rows = []
    day = date_from
    while day <= date_to:
        values = grouped[day]
        rows.append(
            {
                "date": day,
                "date_iso": day.isoformat(),
                "sent": values["sent"],
                "responded": values["responded"],
                "no_response": values["sent"] - values["responded"],
                "qualified": values["qualified"],
                "visit": values["visit"],
                "repeated": values["repeated"],
                "response_pct": _percent(values["responded"], values["sent"]),
            }
        )
        day += timedelta(days=1)
    peak = max((row["sent"] for row in rows), default=0)
    for row in rows:
        row["sent_bar_pct"] = _percent(row["sent"], peak)
        row["responded_bar_pct"] = _percent(row["responded"], peak)
        for plant in row["plants"]:
            plant["sent_share"] = _percent(plant["sent"], row["sent"])
    return rows


def get_remarketing_dashboard(
    date_from,
    date_to,
    *,
    agent_id=None,
    outcome="all",
    plantilla=None,
    granularidad="dia",
):
    """Analiza los lanzamientos de remarketing de TODAS las plantillas activas.

    Cada plantilla es INDEPENDIENTE y se mide por separado (con sus propios
    intentos: 1er envío y reenvíos de la MISMA plantilla). ``plantilla``
    (codigo) opcional filtra a una; ``granularidad`` (dia/semana/mes) define el
    paso de la serie temporal.
    """

    rows = _lead_rows()
    assessments = _assessment_map(rows)
    all_events = []
    reference_time = timezone.now()
    for row in rows:
        lead_id = int(row["id"])
        assessment = assessments.get(
            (lead_id, conversation_hash(row.get("chat_history")))
        )
        launches = detect_remarketing_launches(row.get("chat_history"))
        for position, launch in enumerate(launches):
            launch_date = launch["timestamp"].astimezone(LIMA_TIMEZONE).date()
            if launch_date < date_from or launch_date > date_to:
                continue
            next_launch_at = (
                launches[position + 1]["timestamp"]
                if position + 1 < len(launches)
                else None
            )
            responded = launch["response_at"] is not None
            qualified_after = _after_launch(
                assessment, "qualified", launch["timestamp"], next_launch_at
            )
            visit_after = _after_launch(
                assessment, "visit_intent", launch["timestamp"], next_launch_at
            )
            age_seconds = max(
                0, int((reference_time - launch["timestamp"]).total_seconds())
            )
            all_events.append(
                {
                    "lead_id": lead_id,
                    "display_name": row["display_name"],
                    "agent_id": row.get("agent_id"),
                    "agent_name": row["agent_name"],
                    "status_name": row["status_name"],
                    "campaign_name": row["campaign_name"],
                    "id_chatwoot": row.get("id_chatwoot"),
                    "launch_at": launch["timestamp"],
                    "launch_date": launch_date,
                    "plantilla_codigo": launch.get(
                        "plantilla_codigo", REMARKETING_TEMPLATE_CODE
                    ),
                    "plantilla_titulo": _etiqueta_visual(
                        launch.get("plantilla_titulo", REMARKETING_TEMPLATE_LABEL)
                    ),
                    "remarketing_attempt": int(
                        launch.get("plantilla_orden", REMARKETING_ATTEMPT)
                    ),
                    "launch_sequence_for_lead": int(
                        launch.get("launch_sequence_for_plantilla", position + 1)
                    ),
                    "duplicate_first_attempt": int(
                        launch.get("launch_sequence_for_plantilla", position + 1)
                    ) > 1,
                    "sender": launch["sender"],
                    "sender_label": (
                        "Bot" if launch["sender"] == "bot" else "Agente/flujo"
                    ),
                    "sender_name": launch["sender_name"],
                    "responded": responded,
                    "response_at": launch["response_at"],
                    "response_seconds": launch["response_seconds"],
                    "response_label": duration_label(launch["response_seconds"]),
                    "response_preview": launch["response_text"][:180],
                    "age_seconds": age_seconds,
                    "age_label": duration_label(age_seconds),
                    "qualified_after": qualified_after,
                    "visit_after": visit_after,
                    "qualified_current": bool(
                        assessment and assessment.qualified_status == "confirmed"
                    ),
                    "visit_current": bool(
                        assessment and assessment.visit_intent_status == "confirmed"
                    ),
                    "assessment_pending": assessment is None,
                    "assessment_reason": assessment.reason if assessment else "",
                    "quality_status": (
                        assessment.first_response_status if assessment else None
                    ),
                    "delay_from_previous_label": duration_label(
                        launch["delay_from_previous_seconds"]
                    ),
                }
            )

    agent_options = sorted(
        {(event["agent_id"], event["agent_name"]) for event in all_events},
        key=lambda value: value[1],
    )
    try:
        selected_agent_id = int(agent_id) if agent_id not in (None, "") else None
    except (TypeError, ValueError):
        selected_agent_id = None
    if selected_agent_id is not None:
        events = [event for event in all_events if event["agent_id"] == selected_agent_id]
    else:
        events = list(all_events)

    # ── Plantillas activas: cada plantilla es INDEPENDIENTE (N dinámico) ──
    granularidad = granularidad if granularidad in {"dia", "semana", "mes"} else "dia"
    plantillas_activas = _plantillas_activas()
    color_por_codigo = {
        plantilla["codigo"]: _color_plantilla(idx)
        for idx, plantilla in enumerate(plantillas_activas)
    }
    plantilla_options = [
        {
            "codigo": plantilla.get("codigo"),
            "titulo": _etiqueta_visual(plantilla.get("titulo")),
            "orden": plantilla.get("orden"),
            "color": color_por_codigo.get(plantilla.get("codigo"), "#58a6ff"),
        }
        for plantilla in plantillas_activas
    ]
    etiqueta_por_codigo = {
        plantilla["codigo"]: _etiqueta_visual(plantilla["titulo"])
        for plantilla in plantillas_activas
    }

    # Resumen por plantilla: TODAS las activas (aunque tengan 0 envíos), con
    # sus propios intentos: 1er envío vs reenvíos de la MISMA plantilla.
    resumen = {}
    for plantilla in plantillas_activas:
        codigo = plantilla["codigo"]
        resumen[codigo] = {
            "codigo": codigo,
            "titulo": _etiqueta_visual(plantilla["titulo"]),
            "color": color_por_codigo.get(codigo, "#58a6ff"),
            "sent": 0,
            "sent_first": 0,
            "sent_follow": 0,
            "responded": 0,
            "responded_first": 0,
            "responded_follow": 0,
            "qualified": 0,
            "visit": 0,
            "_leads": set(),
        }
    for event in events:
        dato = resumen.get(event["plantilla_codigo"])
        if dato is None:
            continue
        dato["sent"] += 1
        dato["_leads"].add(event["lead_id"])
        if not event["duplicate_first_attempt"]:
            dato["sent_first"] += 1
            dato["responded_first"] += int(event["responded"])
        else:
            dato["sent_follow"] += 1
            dato["responded_follow"] += int(event["responded"])
        dato["responded"] += int(event["responded"])
        dato["qualified"] += int(event["qualified_after"])
        dato["visit"] += int(event["visit_after"])

    plantillas_resumen = []
    for codigo in sorted(
        resumen.keys(), key=lambda c: (resumen[c]["titulo"].lower(), c)
    ):
        dato = resumen[codigo]
        sent = dato["sent"]
        plantillas_resumen.append(
            {
                "codigo": codigo,
                "titulo": dato["titulo"],
                "color": dato["color"],
                "sent": sent,
                "unique_leads": len(dato["_leads"]),
                "sent_first": dato["sent_first"],
                "sent_follow": dato["sent_follow"],
                "responded": dato["responded"],
                "responded_first": dato["responded_first"],
                "responded_follow": dato["responded_follow"],
                "response_pct": _percent(dato["responded"], sent),
                "response_pct_first": _percent(
                    dato["responded_first"], dato["sent_first"]
                ),
                "response_pct_follow": _percent(
                    dato["responded_follow"], dato["sent_follow"]
                ),
                "qualified": dato["qualified"],
                "visit": dato["visit"],
            }
        )

    valid_codes = {pl["codigo"] for pl in plantilla_options}
    selected_plantilla = (
        plantilla
        if isinstance(plantilla, str) and plantilla in valid_codes
        else None
    )
    if selected_plantilla:
        events = [
            event
            for event in events
            if event["plantilla_codigo"] == selected_plantilla
        ]

    timeline_rows = _timeline_rows(
        events, date_from, date_to, granularidad, plantillas_activas
    )
    total = len(events)
    responded = sum(event["responded"] for event in events)
    qualified = sum(event["qualified_after"] for event in events)
    visits = sum(event["visit_after"] for event in events)
    unique_leads = len({event["lead_id"] for event in events})
    per_lead_counts = Counter(event["lead_id"] for event in events)
    repeated_sends = sum(event["duplicate_first_attempt"] for event in events)
    responded_unique = len(
        {event["lead_id"] for event in events if event["responded"]}
    )

    grouped_agents = defaultdict(list)
    for event in events:
        grouped_agents[(event["agent_id"], event["agent_name"])].append(event)
    agent_rows = []
    for (row_agent_id, agent_name), group in grouped_agents.items():
        group_responded = sum(event["responded"] for event in group)
        agent_rows.append(
            {
                "agent_id": row_agent_id,
                "agent_name": agent_name,
                "sent": len(group),
                "responded": group_responded,
                "no_response": len(group) - group_responded,
                "response_pct": _percent(group_responded, len(group)),
                "qualified": sum(event["qualified_after"] for event in group),
                "visit": sum(event["visit_after"] for event in group),
            }
        )
    agent_rows.sort(key=lambda item: (-item["sent"], item["agent_name"]))

    no_response_events = [event for event in events if not event["responded"]]
    status_counts = Counter(event["status_name"] for event in no_response_events)
    no_response_statuses = [
        {
            "status_name": status,
            "count": count,
            "pct": _percent(count, len(no_response_events)),
        }
        for status, count in status_counts.most_common()
    ]
    loss_patterns = [
        {
            "code": "repeated_attempt_1",
            "label": "Reenvíos de la misma plantilla (intento 2+)",
            "count": repeated_sends,
            "detail": "Un lead ya recibió esta plantilla y se le reenvió la MISMA plantilla (2º, 3º… intento).",
        },
        {
            "code": "no_response_24h",
            "label": "Sin respuesta después de 24 h",
            "count": sum(
                not event["responded"] and event["age_seconds"] >= 24 * 3600
                for event in events
            ),
            "detail": "El remarketing salió, pero el cliente no volvió a escribir.",
        },
        {
            "code": "responded_not_qualified",
            "label": "Respondieron sin calificación confirmada",
            "count": sum(
                event["responded"] and not event["qualified_after"]
                for event in events
            ),
            "detail": "Hubo reacción, pero la IA no detectó interés comercial confirmado después del envío.",
        },
        {
            "code": "qualified_without_visit",
            "label": "Calificados sin intención de visita posterior",
            "count": sum(
                event["qualified_after"] and not event["visit_after"]
                for event in events
            ),
            "detail": "La conversación avanzó, pero todavía no llegó a una intención real de visita.",
        },
        {
            "code": "assessment_pending",
            "label": "Sin evaluación IA vigente",
            "count": sum(event["assessment_pending"] for event in events),
            "detail": "El historial cambió y aún no existe una evaluación contextual para su versión actual.",
        },
    ]

    valid_outcomes = {value for value, _ in OUTCOME_OPTIONS}
    selected_outcome = outcome if outcome in valid_outcomes else "all"
    detail_events = events
    if selected_outcome == "responded":
        detail_events = [event for event in events if event["responded"]]
    elif selected_outcome == "no_response":
        detail_events = [event for event in events if not event["responded"]]
    elif selected_outcome == "qualified":
        detail_events = [event for event in events if event["qualified_after"]]
    elif selected_outcome == "visit":
        detail_events = [event for event in events if event["visit_after"]]
    detail_events.sort(key=lambda item: item["launch_at"], reverse=True)

    return {
        "generated_at": reference_time,
        "date_from": date_from,
        "date_to": date_to,
        "analysis_version": ANALYSIS_VERSION,
        "template_code": (
            selected_plantilla
            or (plantilla_options[0]["codigo"] if plantilla_options else REMARKETING_TEMPLATE_CODE)
        ),
        "template_label": (
            etiqueta_por_codigo.get(selected_plantilla)
            if selected_plantilla
            else (
                plantilla_options[0]["titulo"]
                if plantilla_options
                else REMARKETING_TEMPLATE_LABEL
            )
        ),
        "remarketing_attempt": (
            int(
                next(
                    (
                        plantilla["orden"]
                        for plantilla in plantilla_options
                        if plantilla["codigo"] == selected_plantilla
                    ),
                    1,
                )
            )
            if selected_plantilla
            else (
                int(plantilla_options[0]["orden"])
                if plantilla_options
                else REMARKETING_ATTEMPT
            )
        ),
        "plantillas": plantilla_options,
        "plantillas_resumen": plantillas_resumen,
        "selected_plantilla": selected_plantilla,
        "agent_options": agent_options,
        "selected_agent_id": selected_agent_id,
        "outcome_options": OUTCOME_OPTIONS,
        "selected_outcome": selected_outcome,
        "granularidad": granularidad,
        "granularidad_options": GRANULARIDAD_OPTIONS,
        "summary": {
            "sent": total,
            "unique_leads": unique_leads,
            "repeated_sends": repeated_sends,
            "leads_with_repeats": sum(count > 1 for count in per_lead_counts.values()),
            "max_sends_per_lead": max(per_lead_counts.values(), default=0),
            "average_sends_per_lead": (
                round(total / unique_leads, 1) if unique_leads else 0
            ),
            "responded": responded,
            "responded_unique": responded_unique,
            "no_response": total - responded,
            "response_pct": _percent(responded, total),
            "qualified": qualified,
            "qualified_pct": _percent(qualified, total),
            "visit": visits,
            "visit_pct": _percent(visits, total),
            "median_response_label": _median_label(
                event["response_seconds"] for event in events
            ),
        },
        "daily_rows": timeline_rows,
        "timeline_rows": timeline_rows,
        "agent_rows": agent_rows,
        "no_response_statuses": no_response_statuses,
        "loss_patterns": loss_patterns,
        "events": detail_events[:200],
        "events_total": len(detail_events),
    }


# ─────────────────────────────────────────────────────────────────────────
# API / gestión de plantillas (para la UI del dashboard de remarketing)
# ─────────────────────────────────────────────────────────────────────────
def listar_plantillas_ui():
    """Todas las plantillas (activas e inactivas) para la UI de gestión."""
    from .models import PlantillaMensaje

    try:
        return list(
            PlantillaMensaje.objects.using("default")
            .order_by("orden", "id")
            .values(
                "id",
                "codigo",
                "titulo",
                "cuerpo",
                "orden",
                "frase_condicion",
                "regex_condicion",
                "sql_hint",
                "activa",
            )
        )
    except Exception:  # noqa: BLE001
        return []


def analizar_mensaje(texto):
    """Devuelve qué plantillas activas matchean un mensaje (analizador)."""
    return [
        {
            "codigo": plantilla["codigo"],
            "titulo": _etiqueta_visual(plantilla["titulo"]),
            "orden": plantilla.get("orden"),
        }
        for plantilla in detectar_plantillas(texto)
    ]


def guardar_plantilla(
    *,
    codigo=None,
    titulo="",
    cuerpo="",
    orden=1,
    frase_condicion="",
    regex_condicion="",
    sql_hint="",
    activa=True,
):
    """Crea o actualiza una plantilla de mensaje (codigo como clave)."""
    from .models import PlantillaMensaje

    codigo = (codigo or "").strip()
    if not codigo or not titulo.strip():
        raise ValueError("Faltan el código o el título de la plantilla.")
    try:
        obj, _created = PlantillaMensaje.objects.using("default").update_or_create(
            codigo=codigo,
            defaults={
                "titulo": titulo.strip(),
                "cuerpo": cuerpo,
                "orden": max(int(orden or 1), 1),
                "frase_condicion": frase_condicion,
                "regex_condicion": regex_condicion,
                "sql_hint": sql_hint,
                "activa": bool(activa),
            },
        )
        return {"id": obj.pk, "codigo": obj.codigo, "titulo": obj.titulo}
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo guardar la plantilla: {exc}") from exc
