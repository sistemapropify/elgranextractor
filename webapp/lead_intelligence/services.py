import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone as datetime_timezone

from django.db import connections
from django.utils import timezone

from .attention_quality import (
    average_or_none,
    duration_label,
    first_response_indices,
    first_response_text,
    median_or_none,
    percentile,
    possible_missing_media,
    response_wait_seconds,
    template_signature,
    validate_initial_request_items,
)
from .contextual_analysis import ANALYSIS_VERSION, conversation_hash
from .conversation_analysis import (
    LIMA_TIMEZONE,
    analyze_chat_history,
    milestone_within_days,
)
from .models import (
    AnalysisRun,
    LeadConversationAssessment,
    LeadConversationReview,
)
from .visit_resolution import apply_visit_resolutions


LEAD_RESULT_STAGES = {
    "entered": "Ingresaron",
    "contacted": "Contactados",
    "bidirectional": "Bidireccionales",
    "qualified": "Calificados",
    "visit_intent": "Intención de visita",
    "visit_registered": "Visita registrada",
    "never_contacted": "Sin primera respuesta",
    "unattended": "Esperando al agente",
    "attention_overdue": "Atención vencida >24 h",
}

ATTENTION_OVERDUE_SECONDS = 24 * 60 * 60


def _dict_rows(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _one(cursor):
    rows = _dict_rows(cursor)
    return rows[0] if rows else {}


def _utc_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=datetime_timezone.utc)
    return value.astimezone(datetime_timezone.utc)


def _load_assignment_timelines(rows):
    """Read assignment changes for the requested leads in one SELECT."""

    lead_ids = sorted({int(row["id"]) for row in rows})
    if not lead_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(lead_ids))
    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                la.lead_id,
                la.created_at AS effective_at,
                TRY_CONVERT(
                    bigint,
                    CASE WHEN ISJSON(la.data_old) = 1
                         THEN JSON_VALUE(la.data_old, '$.assigned_to_id')
                    END
                ) AS old_agent_id,
                COALESCE(
                    NULLIF(
                        LTRIM(RTRIM(CONCAT(old_u.first_name, ' ', old_u.last_name))),
                        ''
                    ),
                    old_u.username,
                    'Sin asignar'
                ) AS old_agent_name,
                TRY_CONVERT(
                    bigint,
                    CASE WHEN ISJSON(la.data_new) = 1
                         THEN JSON_VALUE(la.data_new, '$.assigned_to_id')
                    END
                ) AS new_agent_id,
                COALESCE(
                    NULLIF(
                        LTRIM(RTRIM(CONCAT(new_u.first_name, ' ', new_u.last_name))),
                        ''
                    ),
                    new_u.username,
                    'Sin asignar'
                ) AS new_agent_name,
                la.actor_id,
                COALESCE(
                    NULLIF(
                        LTRIM(RTRIM(CONCAT(actor.first_name, ' ', actor.last_name))),
                        ''
                    ),
                    actor.username,
                    'Sistema'
                ) AS actor_name
            FROM dbo.lead_activity la
            LEFT JOIN dbo.[user] old_u
              ON old_u.id = TRY_CONVERT(
                    bigint,
                    CASE WHEN ISJSON(la.data_old) = 1
                         THEN JSON_VALUE(la.data_old, '$.assigned_to_id')
                    END
                )
            LEFT JOIN dbo.[user] new_u
              ON new_u.id = TRY_CONVERT(
                    bigint,
                    CASE WHEN ISJSON(la.data_new) = 1
                         THEN JSON_VALUE(la.data_new, '$.assigned_to_id')
                    END
                )
            LEFT JOIN dbo.[user] actor ON actor.id = la.actor_id
            WHERE la.lead_id IN ({placeholders})
              AND la.activity_type = 'field_update'
              AND la.field_name = 'assigned_to'
            ORDER BY la.lead_id, la.created_at
            """,
            lead_ids,
        )
        activity_rows = _dict_rows(cursor)

    timelines = {}
    for event in activity_rows:
        event["effective_at"] = _utc_datetime(event["effective_at"])
        timelines.setdefault(event["lead_id"], []).append(event)
    return timelines


def _responsible_at(timeline, moment, current_agent_id, current_agent_name):
    """Resolve the assignee effective at a moment, preserving uncertainty."""

    if not timeline or moment is None:
        return {
            "agent_id": current_agent_id,
            "agent_name": current_agent_name,
            "source": "current",
        }
    moment = _utc_datetime(moment)
    if moment < timeline[0]["effective_at"]:
        first = timeline[0]
        return {
            "agent_id": first["old_agent_id"],
            "agent_name": first["old_agent_name"],
            "source": "activity_before_first_change",
        }
    effective = timeline[0]
    for event in timeline:
        if event["effective_at"] > moment:
            break
        effective = event
    return {
        "agent_id": effective["new_agent_id"],
        "agent_name": effective["new_agent_name"],
        "source": "lead_activity",
    }


def _json_object(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _integer_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _activity_value(payload, field_name):
    """Extract a changed field from both nested and flat activity JSON."""

    if not isinstance(payload, dict):
        return None
    if field_name in payload:
        return payload[field_name]
    identifier = f"{field_name}_id"
    if identifier in payload:
        return payload[identifier]
    fields = payload.get("fields")
    if isinstance(fields, dict):
        return fields.get(field_name, fields.get(identifier))
    return None


def _load_lead_activities(lead_id):
    """Return normalized CRM events for one lead using SELECT-only queries."""

    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            """
            SELECT
                la.id,
                la.activity_type,
                la.related_model,
                la.related_id,
                la.field_name,
                la.data_old,
                la.data_new,
                la.description,
                la.created_at,
                la.actor_id,
                COALESCE(
                    NULLIF(
                        LTRIM(RTRIM(CONCAT(actor.first_name, ' ', actor.last_name))),
                        ''
                    ),
                    actor.username,
                    'Sistema'
                ) AS actor_name
            FROM dbo.lead_activity la
            LEFT JOIN dbo.[user] actor ON actor.id = la.actor_id
            WHERE la.lead_id = %s
               OR (la.related_model = 'lead' AND la.related_id = %s)
            ORDER BY la.created_at, la.id
            """,
            [lead_id, lead_id],
        )
        rows = _dict_rows(cursor)

    status_ids = set()
    user_ids = set()
    property_ids = set()
    for row in rows:
        row["_old"] = _json_object(row.pop("data_old"))
        row["_new"] = _json_object(row.pop("data_new"))
        if row["activity_type"] == "status_change":
            for payload in (row["_old"], row["_new"]):
                value = _integer_id(
                    _activity_value(payload, "lead_status")
                    or _activity_value(payload, "status")
                )
                if value is not None:
                    status_ids.add(value)
        if row.get("field_name") == "assigned_to":
            for payload in (row["_old"], row["_new"]):
                value = _integer_id(_activity_value(payload, "assigned_to"))
                if value is not None:
                    user_ids.add(value)
        if row["activity_type"] == "property_assigned":
            value = _integer_id(row.get("related_id"))
            if value is not None:
                property_ids.add(value)

    status_names = {}
    user_names = {}
    property_names = {}
    with connections["propifai"].cursor() as cursor:
        if status_ids:
            placeholders = ", ".join(["%s"] * len(status_ids))
            cursor.execute(
                f"SELECT id, name FROM dbo.lead_status WHERE id IN ({placeholders})",
                list(status_ids),
            )
            status_names = {row["id"]: row["name"] for row in _dict_rows(cursor)}
        if user_ids:
            placeholders = ", ".join(["%s"] * len(user_ids))
            cursor.execute(
                f"""
                SELECT id, COALESCE(
                    NULLIF(LTRIM(RTRIM(CONCAT(first_name, ' ', last_name))), ''),
                    username,
                    'Usuario'
                ) AS name
                FROM dbo.[user]
                WHERE id IN ({placeholders})
                """,
                list(user_ids),
            )
            user_names = {row["id"]: row["name"] for row in _dict_rows(cursor)}
        if property_ids:
            placeholders = ", ".join(["%s"] * len(property_ids))
            cursor.execute(
                f"""
                SELECT id, code, title
                FROM dbo.property
                WHERE id IN ({placeholders})
                """,
                list(property_ids),
            )
            property_names = {
                row["id"]: " — ".join(
                    item for item in (row.get("code"), row.get("title")) if item
                )
                for row in _dict_rows(cursor)
            }

    labels = {
        "status_change": "Cambio de estado",
        "field_update": "Actualización de campo",
        "property_assigned": "Propiedad asignada",
        "lead_type_set": "Tipo de lead definido",
    }
    events = []
    for row in rows:
        activity_type = row["activity_type"]
        field_name = row.get("field_name")
        old_value = None
        new_value = None
        detail = None
        if activity_type == "status_change":
            old_id = _integer_id(
                _activity_value(row["_old"], "lead_status")
                or _activity_value(row["_old"], "status")
            )
            new_id = _integer_id(
                _activity_value(row["_new"], "lead_status")
                or _activity_value(row["_new"], "status")
            )
            old_value = status_names.get(old_id) if old_id is not None else None
            new_value = status_names.get(new_id) if new_id is not None else None
        elif activity_type == "field_update" and field_name == "assigned_to":
            old_id = _integer_id(_activity_value(row["_old"], "assigned_to"))
            new_id = _integer_id(_activity_value(row["_new"], "assigned_to"))
            old_value = user_names.get(old_id, "Sin asignar")
            new_value = user_names.get(new_id, "Sin asignar")
        elif activity_type == "field_update":
            old_value = _activity_value(row["_old"], field_name)
            new_value = _activity_value(row["_new"], field_name)
        elif activity_type == "property_assigned":
            detail = property_names.get(
                _integer_id(row.get("related_id")),
                f"Propiedad #{row.get('related_id')}",
            )
        elif activity_type == "lead_type_set":
            related_model = (row.get("related_model") or "").lower()
            detail = {
                "buyer_profile": "Lead comprador",
                "seller_profile": "Lead propietario",
            }.get(related_model, related_model.replace("_", " ").title())

        events.append(
            {
                "event_type": "activity",
                "activity_id": row["id"],
                "activity_type": activity_type,
                "activity_label": labels.get(
                    activity_type, activity_type.replace("_", " ").title()
                ),
                "description": row.get("description"),
                "field_name": field_name,
                "actor_name": row.get("actor_name") or "Sistema",
                "related_model": row.get("related_model"),
                "related_id": row.get("related_id"),
                "timestamp": _utc_datetime(row.get("created_at")),
                "change_from": old_value,
                "change_to": new_value,
                "detail": detail,
            }
        )
    return events


def build_daily_incoming(metrics_by_date, date_from, date_to):
    """Return a continuous daily series, including dates with zero leads."""
    series = []
    current_date = date_from
    while current_date <= date_to:
        series.append(
            {
                "date": current_date.isoformat(),
                "count": len(metrics_by_date.get(current_date, [])),
            }
        )
        current_date += timedelta(days=1)
    return series


def _lead_result_rows(date_from, date_to, lead_id=None):
    params = []
    where = []
    if lead_id is not None:
        where.append("l.id = %s")
        params.append(lead_id)
    else:
        where.append(
            """CAST(
                SWITCHOFFSET(COALESCE(l.date_entry, l.created_at), '-05:00')
                AS date
            ) BETWEEN %s AND %s"""
        )
        params.extend([date_from, date_to])
    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                l.id,
                l.assigned_to_id AS agent_id,
                l.chat_history,
                l.id_chatwoot,
                l.source,
                l.source_detail,
                l.budget,
                l.financing,
                l.temperature,
                l.score,
                l.notes,
                COALESCE(l.date_entry, l.created_at) AS entered_at,
                c.first_name,
                c.last_name,
                c.business_name,
                c.phone,
                c.email,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(CONCAT(u.first_name, ' ', u.last_name))), ''),
                    u.username,
                    'Sin asignar'
                ) AS agent_name,
                COALESCE(ls.name, 'Sin estado') AS status_name,
                COALESCE(cl.name, 'Sin canal') AS channel_name
            FROM dbo.lead l
            LEFT JOIN dbo.contact c ON c.id = l.contact_id
            LEFT JOIN dbo.[user] u ON u.id = l.assigned_to_id
            LEFT JOIN dbo.lead_status ls ON ls.id = l.lead_status_id
            LEFT JOIN dbo.canal_lead cl ON cl.id = l.canal_lead_id
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(l.date_entry, l.created_at) DESC, l.id DESC
            """,
            params,
        )
        rows = _dict_rows(cursor)
    return apply_visit_resolutions(rows)


# Horario de atención de negocio: 09:00 a 18:00 (hora de Perú). La hora 18
# (hasta las 18:59) se considera dentro del horario; ajustar estos límites
# si cambia la política de atención.
WORKING_HOURS_START = 9
WORKING_HOURS_END = 18


def _hour_of_day(value):
    """Hora (0-23) en America/Lima del timestamp de ingreso de un lead."""
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=datetime_timezone.utc)
    return parsed.astimezone(LIMA_TIMEZONE).hour


def get_hourly_agent_matrix(date_from, date_to):
    """Matriz de distribución horaria (0-23) de ingresos por agente asignado.

    Devuelve, para el periodo, la cantidad de leads que ingresaron en cada hora
    (America/Lima) descompuesta por el agente asignado al lead, con totales por
    agente, por hora y general, más el resumen dentro/fuera del horario de
    atención (09:00-18:00).
    """
    rows = _lead_result_rows(date_from, date_to)
    agent_cells = {}
    hour_totals = [0] * 24
    grand_total = 0
    working = 0
    outside = 0
    for row in rows:
        hour = _hour_of_day(row.get("entered_at"))
        if hour is None:
            continue
        agent = row.get("agent_name") or "Sin asignar"
        cell = agent_cells.setdefault(agent, {})
        cell[hour] = cell.get(hour, 0) + 1
        hour_totals[hour] += 1
        grand_total += 1
        if WORKING_HOURS_START <= hour <= WORKING_HOURS_END:
            working += 1
        else:
            outside += 1

    def _is_working(hour):
        return WORKING_HOURS_START <= hour <= WORKING_HOURS_END

    agent_rows = [
        {
            "agent": agent,
            "cells": [
                {
                    "count": agent_cells[agent].get(hour, 0),
                    "working": _is_working(hour),
                }
                for hour in range(24)
            ],
            "total": sum(agent_cells[agent].get(hour, 0) for hour in range(24)),
        }
        for agent in sorted(agent_cells)
    ]
    return {
        "hours": [
            {
                "label": f"{hour:02d}:00",
                "working": _is_working(hour),
                "total": hour_totals[hour],
            }
            for hour in range(24)
        ],
        "agent_rows": agent_rows,
        "grand_total": grand_total,
        "working": working,
        "outside": outside,
        "working_pct": _percentage(working, grand_total),
        "outside_pct": _percentage(outside, grand_total),
    }


def _assessment_map(rows):
    keys = {
        (row["id"], conversation_hash(row.get("chat_history")))
        for row in rows
    }
    if not keys:
        return {}
    lead_ids = {lead_id for lead_id, _ in keys}
    assessments = (
        LeadConversationAssessment.objects.using("default")
        .filter(
            source_lead_id__in=lead_ids,
            analysis_version=ANALYSIS_VERSION,
        )
        .order_by("-analyzed_at")
    )
    result = {}
    for assessment in assessments:
        key = (assessment.source_lead_id, assessment.history_hash)
        if key in keys and key not in result:
            result[key] = assessment
    return result


def _evidence_timestamp(messages, evidence):
    if not evidence:
        return None
    try:
        index = int(evidence[0]["message_index"])
    except (KeyError, TypeError, ValueError):
        return None
    return messages[index]["timestamp"] if 0 <= index < len(messages) else None


def _apply_contextual_assessment(analysis, assessment):
    analysis["context_assessment"] = assessment
    analysis["context_analysis_pending"] = (
        assessment is None and bool(analysis["messages"])
    )
    if assessment is None:
        analysis["qualified"] = False
        analysis["qualified_at"] = None
        analysis["visit_intent"] = False
        analysis["visit_intent_at"] = None
        return analysis
    analysis["qualified"] = (
        analysis["bidirectional"]
        and assessment.qualified_status
        == LeadConversationAssessment.Decision.CONFIRMED
    )
    analysis["qualified_at"] = (
        _evidence_timestamp(
            analysis["messages"], assessment.qualified_evidence
        )
        if analysis["qualified"]
        else None
    )
    analysis["visit_intent"] = (
        assessment.visit_intent_status
        == LeadConversationAssessment.Decision.CONFIRMED
    )
    analysis["visit_intent_at"] = (
        _evidence_timestamp(
            analysis["messages"], assessment.visit_intent_evidence
        )
        if analysis["visit_intent"]
        else None
    )
    return analysis


def _prepare_lead_result(row, assessment=None, assignment_timeline=None):
    assignment_timeline = assignment_timeline or []
    analysis = _apply_contextual_assessment(
        analyze_chat_history(row.pop("chat_history")), assessment
    )
    first_name = (row.pop("first_name") or "").strip()
    last_name = (row.pop("last_name") or "").strip()
    business_name = (row.pop("business_name") or "").strip()
    row["display_name"] = (
        f"{first_name} {last_name}".strip()
        or business_name
        or f"Lead #{row['id']}"
    )
    responsible = _responsible_at(
        assignment_timeline,
        analysis["first_agent_response_at"],
        row.get("agent_id"),
        row["agent_name"],
    )
    row["agent_at_first_response_id"] = responsible["agent_id"]
    row["agent_at_first_response_name"] = responsible["agent_name"]
    row["agent_at_first_response_source"] = responsible["source"]
    row["assignment_timeline"] = assignment_timeline
    row["media_gap_risk"] = possible_missing_media(analysis["messages"])
    row["visit_registered"] = row["first_visit_at"] is not None
    row["never_contacted"] = (
        analysis["first_lead_at"] is not None and not analysis["contacted"]
    )
    grounded_items, unsupported_items = validate_initial_request_items(
        analysis["messages"],
        assessment.unanswered_request_items if assessment else [],
    )
    row["attention_unanswered_items"] = grounded_items
    row["attention_unsupported_items"] = unsupported_items
    row["attention_grounding_issue"] = bool(unsupported_items)
    row.update(analysis)
    row.update(_waiting_attention(analysis))
    return row


def get_lead_results(date_from, date_to, stage):
    """Return lead cards for one dashboard stage using SELECT-only CRM access."""
    if stage not in LEAD_RESULT_STAGES:
        stage = "entered"
    rows = _lead_result_rows(date_from, date_to)
    assessments = _assessment_map(rows)
    leads = [
        _prepare_lead_result(
            row,
            assessments.get((row["id"], conversation_hash(row["chat_history"]))),
        )
        for row in rows
    ]
    if stage != "entered":
        leads = [lead for lead in leads if lead.get(stage)]
    return {
        "leads": leads,
        "stage": stage,
        "stage_label": LEAD_RESULT_STAGES[stage],
    }


def get_lead_conversation(lead_id):
    """Return one lead with chat and CRM activity in one chronology."""
    rows = _lead_result_rows(None, None, lead_id=lead_id)
    if not rows:
        return None
    assessments = _assessment_map(rows)
    row = rows[0]
    assessment = assessments.get(
        (row["id"], conversation_hash(row["chat_history"]))
    )
    assignment_timeline = _load_assignment_timelines(rows).get(lead_id, [])
    lead = _prepare_lead_result(row, assessment, assignment_timeline)
    activities = _load_lead_activities(lead_id)
    message_events = [
        {
            **message,
            "event_type": "message",
            "sequence": index,
        }
        for index, message in enumerate(lead["messages"])
    ]
    lead["activity_events"] = activities
    lead["timeline_events"] = sorted(
        message_events + activities,
        key=lambda event: (
            event["timestamp"],
            0 if event["event_type"] == "activity" else 1,
            event.get("activity_id", event.get("sequence", 0)),
        ),
    )
    return lead


def _display_name(row):
    first_name = (row.get("first_name") or "").strip()
    last_name = (row.get("last_name") or "").strip()
    business_name = (row.get("business_name") or "").strip()
    return (
        f"{first_name} {last_name}".strip()
        or business_name
        or f"Lead #{row['id']}"
    )


def _score(value):
    return float(value) if value is not None else None


def _evidence_matches(evidence, sender, allowed_indices=None):
    if not evidence:
        return False
    for item in evidence:
        if not isinstance(item, dict) or item.get("sender") != sender:
            return False
        try:
            index = int(item.get("message_index"))
        except (TypeError, ValueError):
            return False
        if allowed_indices is not None and index not in allowed_indices:
            return False
    return True


def _percentage(numerator, denominator):
    return round(numerator / denominator * 100, 1) if denominator else 0


def _waiting_attention(analysis, reference_time=None):
    """Measure the open lead turn without changing the CRM lead status."""

    if not analysis["unattended"] or analysis["last_message_at"] is None:
        return {
            "unattended_seconds": None,
            "unattended_label": "—",
            "attention_overdue": False,
        }
    reference_time = _utc_datetime(reference_time or timezone.now())
    last_message_at = _utc_datetime(analysis["last_message_at"])
    seconds = max(0, int((reference_time - last_message_at).total_seconds()))
    return {
        "unattended_seconds": seconds,
        "unattended_label": duration_label(seconds),
        "attention_overdue": seconds >= ATTENTION_OVERDUE_SECONDS,
    }


def get_attention_quality_dashboard(
    date_from: date,
    date_to: date,
    agent_id=None,
):
    """Measure response speed and first-response quality by assigned agent."""

    rows = _lead_result_rows(date_from, date_to)
    assessments = _assessment_map(rows)
    assignment_timelines = _load_assignment_timelines(rows)
    reference_time = timezone.now()
    items = []
    for row in rows:
        history_hash = conversation_hash(row["chat_history"])
        assessment = assessments.get((row["id"], history_hash))
        analysis = _apply_contextual_assessment(
            analyze_chat_history(row["chat_history"]),
            assessment,
        )
        waits = response_wait_seconds(analysis["messages"])
        response_text = first_response_text(analysis["messages"])
        valid_first_response_indexes = first_response_indices(
            analysis["messages"]
        )
        first_response_evidence_valid = bool(
            assessment
            and _evidence_matches(
                assessment.first_response_evidence,
                "agent",
                valid_first_response_indexes,
            )
        )
        quality_status = (
            assessment.first_response_status if assessment else None
        )
        media_gap_risk = possible_missing_media(analysis["messages"])
        grounded_items, unsupported_items = validate_initial_request_items(
            analysis["messages"],
            assessment.unanswered_request_items if assessment else [],
        )
        if (
            quality_status in {"adequate", "partial", "inadequate"}
            and not first_response_evidence_valid
        ):
            quality_status = "ambiguous"
        if media_gap_risk and quality_status not in (None, "not_applicable"):
            quality_status = "ambiguous"
        if unsupported_items and quality_status not in (None, "not_applicable"):
            quality_status = "ambiguous"
        responsible = _responsible_at(
            assignment_timelines.get(row["id"], []),
            analysis["first_agent_response_at"],
            row.get("agent_id"),
            row["agent_name"],
        )
        waiting_attention = _waiting_attention(analysis, reference_time)
        items.append(
            {
                "lead_id": row["id"],
                "history_hash": history_hash,
                "display_name": _display_name(row),
                "agent_id": responsible["agent_id"],
                "agent_name": responsible["agent_name"],
                "current_agent_id": row.get("agent_id"),
                "current_agent_name": row["agent_name"],
                "attribution_source": responsible["source"],
                "assignment_changes": len(
                    assignment_timelines.get(row["id"], [])
                ),
                "media_gap_risk": media_gap_risk,
                "attention_grounding_issue": bool(unsupported_items),
                "unsupported_request_items": unsupported_items,
                "channel_name": row["channel_name"],
                "entered_at": row["entered_at"],
                "contacted": analysis["contacted"],
                "bidirectional": analysis["bidirectional"],
                "qualified": analysis["qualified"],
                "unattended": analysis["unattended"],
                **waiting_attention,
                "first_response_seconds": analysis["first_response_seconds"],
                "first_response_label": duration_label(
                    analysis["first_response_seconds"]
                ),
                "response_waits": waits,
                "response_text": response_text,
                "response_preview": response_text[:240],
                "template_signature": template_signature(response_text),
                "assessment": assessment,
                "quality_status": quality_status,
                "quality_status_label": (
                    dict(
                        LeadConversationAssessment.AttentionDecision.choices
                    ).get(quality_status, "Pendiente")
                ),
                "quality_confidence": (
                    _score(assessment.first_response_confidence)
                    if assessment
                    else None
                ),
                "relevance_score": (
                    _score(assessment.relevance_score)
                    if assessment
                    else None
                ),
                "coverage_score": (
                    _score(assessment.coverage_score)
                    if assessment
                    else None
                ),
                "directness_score": (
                    _score(assessment.directness_score)
                    if assessment
                    else None
                ),
                "personalization_score": (
                    _score(assessment.personalization_score)
                    if assessment
                    else None
                ),
                "unanswered_items": (
                    grounded_items
                ),
                "attention_reason": (
                    assessment.attention_reason
                    if assessment and not unsupported_items
                    else ""
                ),
            }
        )

    signature_counts = Counter(
        item["template_signature"]
        for item in items
        if item["template_signature"]
    )
    for item in items:
        frequency = signature_counts.get(item["template_signature"], 0)
        item["template_frequency"] = frequency
        item["repeated_template"] = frequency >= 3

    agent_options = sorted(
        {
            (item["agent_id"], item["agent_name"])
            for item in items
        },
        key=lambda item: item[1],
    )
    if agent_id not in (None, ""):
        try:
            selected_agent_id = int(agent_id)
        except (TypeError, ValueError):
            selected_agent_id = None
        if selected_agent_id is not None:
            items = [
                item
                for item in items
                if item["agent_id"] == selected_agent_id
            ]
    else:
        selected_agent_id = None

    def aggregate(group_items, name=None, group_agent_id=None):
        contacted = [item for item in group_items if item["contacted"]]
        assessed = [
            item
            for item in group_items
            if item["quality_status"] in {"adequate", "partial", "inadequate"}
            and not item["media_gap_risk"]
            and not item["attention_grounding_issue"]
        ]
        first_times = [
            item["first_response_seconds"]
            for item in contacted
            if item["first_response_seconds"] is not None
        ]
        all_waits = [
            wait
            for item in group_items
            for wait in item["response_waits"]
        ]
        adequate = sum(
            item["quality_status"] == "adequate" for item in assessed
        )
        templates = sum(item["repeated_template"] for item in contacted)
        return {
            "agent_id": group_agent_id,
            "agent_name": name,
            "leads": len(group_items),
            "contacted": len(contacted),
            "bidirectional": sum(
                item["bidirectional"] for item in group_items
            ),
            "qualified": sum(item["qualified"] for item in group_items),
            "unattended": sum(item["unattended"] for item in group_items),
            "attention_overdue": sum(
                item["attention_overdue"] for item in group_items
            ),
            "quality_assessed": len(assessed),
            "first_response_count": len(first_times),
            "adequate": adequate,
            "partial": sum(
                item["quality_status"] == "partial" for item in assessed
            ),
            "inadequate": sum(
                item["quality_status"] == "inadequate" for item in assessed
            ),
            "median_first_response": median_or_none(first_times),
            "median_first_response_label": duration_label(
                median_or_none(first_times)
            ),
            "p75_first_response_label": duration_label(
                percentile(first_times, 75)
            ),
            "p90_first_response_label": duration_label(
                percentile(first_times, 90)
            ),
            "median_turn_response_label": duration_label(
                median_or_none(all_waits)
            ),
            "sla_15_count": sum(value <= 900 for value in first_times),
            "sla_15_pct": _percentage(
                sum(value <= 900 for value in first_times),
                len(first_times),
            ),
            "sla_60_pct": _percentage(
                sum(value <= 3600 for value in first_times),
                len(first_times),
            ),
            "adequate_pct": _percentage(adequate, len(assessed)),
            "avg_relevance": average_or_none(
                item["relevance_score"] for item in assessed
            ),
            "avg_coverage": average_or_none(
                item["coverage_score"] for item in assessed
            ),
            "avg_directness": average_or_none(
                item["directness_score"] for item in assessed
            ),
            "avg_personalization": average_or_none(
                item["personalization_score"] for item in assessed
            ),
            "template_count": templates,
            "template_pct": _percentage(templates, len(contacted)),
            "bidirectional_from_contacted_pct": _percentage(
                sum(item["bidirectional"] for item in group_items),
                len(contacted),
            ),
        }

    grouped = {}
    for item in items:
        key = item["agent_id"] or "unassigned"
        grouped.setdefault(key, []).append(item)
    agent_rows = [
        aggregate(
            group_items,
            group_items[0]["agent_name"],
            group_items[0]["agent_id"],
        )
        for group_items in grouped.values()
    ]
    agent_rows.sort(
        key=lambda row: (-row["leads"], row["agent_name"])
    )
    comparable_quality = [
        row["adequate_pct"]
        for row in agent_rows
        if row["quality_assessed"] >= 5
    ]
    comparable_speed = [
        row["median_first_response"]
        for row in agent_rows
        if row["first_response_count"] >= 5
        and row["median_first_response"] is not None
    ]
    for row in agent_rows:
        if (
            row["quality_assessed"] < 5
            or len(comparable_quality) < 2
            or max(comparable_quality) == min(comparable_quality)
        ):
            row["quality_tone"] = "neutral"
        elif row["adequate_pct"] == max(comparable_quality):
            row["quality_tone"] = "highest"
        elif row["adequate_pct"] == min(comparable_quality):
            row["quality_tone"] = "lowest"
        else:
            row["quality_tone"] = "middle"
        if (
            row["first_response_count"] < 5
            or len(comparable_speed) < 2
            or max(comparable_speed) == min(comparable_speed)
        ):
            row["speed_tone"] = "neutral"
        elif row["median_first_response"] == min(comparable_speed):
            row["speed_tone"] = "highest"
        elif row["median_first_response"] == max(comparable_speed):
            row["speed_tone"] = "lowest"
        else:
            row["speed_tone"] = "middle"

    overall = aggregate(items)
    overall["quality_pending"] = sum(
        item["contacted"] and item["quality_status"] is None
        for item in items
    )
    overall["slow_over_60"] = sum(
        item["first_response_seconds"] is not None
        and item["first_response_seconds"] > 3600
        for item in items
    )
    overall["media_unobservable"] = sum(
        item["media_gap_risk"] for item in items
    )
    overall["with_assignment_changes"] = sum(
        item["assignment_changes"] > 0 for item in items
    )

    flagged = []
    for item in items:
        issues = []
        if item["attention_overdue"]:
            issues.append(
                f"Atención vencida: {item['unattended_label']} sin respuesta"
            )
        if item["attention_grounding_issue"]:
            issues.append("La IA infirió solicitudes no expresadas por el lead")
        if item["media_gap_risk"]:
            issues.append("Multimedia de Chatwoot no observable")
        if item["quality_status"] == "inadequate":
            issues.append("Primera respuesta inadecuada")
        elif item["quality_status"] == "partial":
            issues.append("Respuesta parcial")
        if item["unanswered_items"] and not item["media_gap_risk"]:
            issues.append(
                f"{len(item['unanswered_items'])} solicitud(es) no cubierta(s) "
                "en la primera respuesta"
            )
        if (
            item["first_response_seconds"] is not None
            and item["first_response_seconds"] > 3600
        ):
            issues.append("Primera respuesta mayor a 1 hora")
        if item["repeated_template"]:
            issues.append(
                f"Respuesta repetida en {item['template_frequency']} leads"
            )
        if issues:
            item["issues"] = issues
            flagged.append(item)
    flagged.sort(
        key=lambda item: (
            not item["attention_overdue"],
            item["quality_status"] != "inadequate",
            -(item["unattended_seconds"] or item["first_response_seconds"] or 0),
        )
    )

    return {
        "generated_at": timezone.now(),
        "date_from": date_from,
        "date_to": date_to,
        "analysis_version": ANALYSIS_VERSION,
        "selected_agent_id": selected_agent_id,
        "agent_options": agent_options,
        "overall": overall,
        "agent_rows": agent_rows,
        "flagged_leads": flagged[:100],
    }


def get_analysis_quality_dashboard(date_from: date, date_to: date):
    """Observe and audit the contextual classification engine."""

    rows = _lead_result_rows(date_from, date_to)
    row_by_id = {row["id"]: row for row in rows}
    analyses = {
        row["id"]: analyze_chat_history(row["chat_history"])
        for row in rows
    }
    analyzable_ids = {
        lead_id
        for lead_id, analysis in analyses.items()
        if analysis["messages"]
    }
    hashes = {
        row["id"]: conversation_hash(row["chat_history"])
        for row in rows
    }
    assessments = list(
        LeadConversationAssessment.objects.using("default")
        .filter(
            source_lead_id__in=analyzable_ids,
            analysis_version=ANALYSIS_VERSION,
        )
        .order_by("-analyzed_at")
    )
    current = {}
    for assessment in assessments:
        lead_id = assessment.source_lead_id
        if (
            hashes.get(lead_id) == assessment.history_hash
            and lead_id not in current
        ):
            current[lead_id] = assessment

    reviews = list(
        LeadConversationReview.objects.using("default").filter(
            source_lead_id__in=current,
            analysis_version=ANALYSIS_VERSION,
        )
    )
    reviews = [
        review
        for review in reviews
        if (
            review.source_lead_id in current
            and review.history_hash
            == current[review.source_lead_id].history_hash
        )
    ]
    review_map = {
        (
            review.source_lead_id,
            review.history_hash,
            review.stage,
        ): review
        for review in reviews
    }

    decision_counts = {
        "qualified": Counter(),
        "visit_intent": Counter(),
        "first_response": Counter(),
    }
    confidence_values = []
    evidence_issues = 0
    queue = []
    source_gap_ids = {
        lead_id
        for lead_id, analysis in analyses.items()
        if possible_missing_media(analysis["messages"])
    }

    stage_specs = (
        (
            "qualified",
            "Calificación",
            "qualified_status",
            "qualified_confidence",
            "qualified_evidence",
            LeadConversationAssessment.Decision.choices,
        ),
        (
            "visit_intent",
            "Intención de visita",
            "visit_intent_status",
            "visit_intent_confidence",
            "visit_intent_evidence",
            LeadConversationAssessment.Decision.choices,
        ),
        (
            "first_response",
            "Primera respuesta",
            "first_response_status",
            "first_response_confidence",
            "first_response_evidence",
            LeadConversationAssessment.AttentionDecision.choices,
        ),
    )

    high_confidence_samples = []
    for lead_id, assessment in current.items():
        for (
            stage,
            stage_label,
            status_field,
            confidence_field,
            evidence_field,
            choices,
        ) in stage_specs:
            ai_value = getattr(assessment, status_field)
            if ai_value is None:
                continue
            confidence = _score(getattr(assessment, confidence_field)) or 0
            evidence = getattr(assessment, evidence_field) or []
            if stage == "first_response":
                evidence_valid = _evidence_matches(
                    evidence,
                    "agent",
                    first_response_indices(
                        analyses[lead_id]["messages"]
                    ),
                )
            else:
                evidence_valid = _evidence_matches(evidence, "lead")
            decision_counts[stage][ai_value] += 1
            confidence_values.append(confidence)
            if ai_value in {"confirmed", "adequate", "partial", "inadequate"}:
                if not evidence_valid:
                    evidence_issues += 1
            review = review_map.get(
                (lead_id, assessment.history_hash, stage)
            )
            reasons = []
            media_gap_risk = (
                stage == "first_response" and lead_id in source_gap_ids
            )
            unsupported_request_items = []
            if stage == "first_response":
                _, unsupported_request_items = validate_initial_request_items(
                    analyses[lead_id]["messages"],
                    assessment.unanswered_request_items,
                )
            if media_gap_risk:
                reasons.append("Multimedia no observable en chat_history")
            if unsupported_request_items:
                reasons.append("La IA infirió solicitudes no expresadas")
            if ai_value == "ambiguous":
                reasons.append("Decisión ambigua")
            if confidence < 0.75:
                reasons.append("Confianza menor a 75%")
            if (
                ai_value in {"confirmed", "adequate", "partial", "inadequate"}
                and not evidence_valid
            ):
                reasons.append("Sin evidencia válida")
            entry = {
                "lead_id": lead_id,
                "display_name": _display_name(row_by_id[lead_id]),
                "agent_name": row_by_id[lead_id]["agent_name"],
                "stage": stage,
                "stage_label": stage_label,
                "ai_value": ai_value,
                "ai_label": dict(choices).get(ai_value, ai_value),
                "confidence": confidence,
                "reason": (
                    assessment.attention_reason
                    if stage == "first_response"
                    else assessment.reason
                ),
                "review": review,
                "review_reasons": reasons,
                "media_gap_risk": media_gap_risk,
                "unsupported_request_items": unsupported_request_items,
                "human_choices": list(choices),
                "history_hash": assessment.history_hash,
                "analysis_version": assessment.analysis_version,
            }
            if reasons:
                queue.append(entry)
            elif review is None and confidence >= 0.85:
                high_confidence_samples.append(entry)

    reviewed_keys = {
        (item["lead_id"], item["history_hash"], item["stage"])
        for item in queue
        if item["review"] is not None
    }
    queue.extend(
        item
        for item in high_confidence_samples[:12]
        if (
            item["lead_id"],
            item["history_hash"],
            item["stage"],
        )
        not in reviewed_keys
    )
    queue.sort(
        key=lambda item: (
            not item["review_reasons"],
            item["confidence"],
            item["lead_id"],
        )
    )

    decisive_reviews = [
        review
        for review in reviews
        if review.verdict != LeadConversationReview.Verdict.UNSURE
    ]
    correct_reviews = sum(
        review.verdict == LeadConversationReview.Verdict.CORRECT
        for review in decisive_reviews
    )
    false_positives = sum(
        review.ai_value in {"confirmed", "adequate"}
        and review.human_value in {"not_confirmed", "inadequate"}
        for review in decisive_reviews
    )
    false_negatives = sum(
        review.ai_value in {"not_confirmed", "inadequate"}
        and review.human_value in {"confirmed", "adequate"}
        for review in decisive_reviews
    )

    confidence_buckets = [
        {
            "label": "< 60%",
            "count": sum(value < 0.60 for value in confidence_values),
        },
        {
            "label": "60–74%",
            "count": sum(
                0.60 <= value < 0.75 for value in confidence_values
            ),
        },
        {
            "label": "75–89%",
            "count": sum(
                0.75 <= value < 0.90 for value in confidence_values
            ),
        },
        {
            "label": "≥ 90%",
            "count": sum(value >= 0.90 for value in confidence_values),
        },
    ]
    runs = list(
        AnalysisRun.objects.using("default")
        .filter(rules_version=ANALYSIS_VERSION)
        .order_by("-started_at")[:10]
    )
    for run in runs:
        run.processed = (
            run.leads_analyzed + run.leads_skipped + run.leads_failed
        )
        run.progress_pct = _percentage(
            run.processed,
            run.leads_total,
        )

    return {
        "generated_at": timezone.now(),
        "date_from": date_from,
        "date_to": date_to,
        "analysis_version": ANALYSIS_VERSION,
        "total_leads": len(rows),
        "analyzable": len(analyzable_ids),
        "analyzed": len(current),
        "pending": len(analyzable_ids) - len(current),
        "coverage_pct": _percentage(len(current), len(analyzable_ids)),
        "ambiguous": sum(
            counter["ambiguous"] for counter in decision_counts.values()
        ),
        "low_confidence": sum(
            value < 0.75 for value in confidence_values
        ),
        "evidence_issues": evidence_issues,
        "source_gaps": len(source_gap_ids),
        "reviewed": len(reviews),
        "decisive_reviews": len(decisive_reviews),
        "agreement_pct": _percentage(
            correct_reviews, len(decisive_reviews)
        ),
        "incorrect_reviews": len(decisive_reviews) - correct_reviews,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "decision_counts": decision_counts,
        "decision_total": max(1, len(confidence_values)),
        "confidence_buckets": confidence_buckets,
        "review_queue": queue[:100],
        "runs": runs,
    }


def save_conversation_review(
    *,
    source_lead_id,
    history_hash,
    analysis_version,
    stage,
    verdict,
    human_value,
    notes="",
    reviewed_by=None,
):
    """Validate and persist a human label only in the internal database."""

    stage_fields = {
        LeadConversationReview.Stage.QUALIFIED: (
            "qualified_status",
            {value for value, _ in LeadConversationAssessment.Decision.choices},
        ),
        LeadConversationReview.Stage.VISIT_INTENT: (
            "visit_intent_status",
            {value for value, _ in LeadConversationAssessment.Decision.choices},
        ),
        LeadConversationReview.Stage.FIRST_RESPONSE: (
            "first_response_status",
            {
                value
                for value, _ in
                LeadConversationAssessment.AttentionDecision.choices
            },
        ),
    }
    if stage not in stage_fields:
        raise ValueError("Etapa de revisión inválida.")
    if verdict not in {
        value for value, _ in LeadConversationReview.Verdict.choices
    }:
        raise ValueError("Resultado de revisión inválido.")

    assessment = (
        LeadConversationAssessment.objects.using("default")
        .filter(
            source_lead_id=source_lead_id,
            history_hash=history_hash,
            analysis_version=analysis_version,
        )
        .first()
    )
    if assessment is None:
        raise ValueError("La evaluación ya no está vigente.")
    status_field, allowed_values = stage_fields[stage]
    ai_value = getattr(assessment, status_field)
    if verdict == LeadConversationReview.Verdict.CORRECT:
        human_value = ai_value
    elif (
        verdict == LeadConversationReview.Verdict.UNSURE
        and not human_value
    ):
        human_value = ai_value
    if human_value not in allowed_values:
        raise ValueError("La corrección humana no es válida para esta etapa.")

    review, _ = (
        LeadConversationReview.objects.using("default").update_or_create(
            source_lead_id=source_lead_id,
            history_hash=history_hash,
            analysis_version=analysis_version,
            stage=stage,
            defaults={
                "ai_value": ai_value,
                "human_value": human_value,
                "verdict": verdict,
                "notes": str(notes or "").strip()[:2000],
                "reviewed_by": reviewed_by,
            },
        )
    )
    return review


def get_management_dashboard(
    date_from: date, date_to: date, cohort_date: date | None
):
    """
    Read-only analytics over dbpropify_be.

    All writes generated by Prometeo belong to the default database. This
    service intentionally uses only SELECT statements against `propifai`.
    """
    now = timezone.now()
    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT_BIG(*) AS total_leads,
                SUM(CASE WHEN l.assigned_to_id IS NULL THEN 1 ELSE 0 END) AS unassigned,
                COUNT_BIG(*) AS new_in_period
            FROM dbo.lead l
            WHERE CAST(
                SWITCHOFFSET(COALESCE(l.date_entry, l.created_at), '-05:00')
                AS date
            ) BETWEEN %s AND %s
            """,
            [date_from, date_to],
        )
        overview = _one(cursor)

        cursor.execute(
            """
            SELECT
                l.id,
                CAST(
                    SWITCHOFFSET(COALESCE(l.date_entry, l.created_at), '-05:00')
                    AS date
                ) AS cohort_date,
                l.chat_history,
                l.assigned_to_id AS agent_id,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(CONCAT(u.first_name, ' ', u.last_name))), ''),
                    u.username,
                    'Sin asignar'
                ) AS agent_name
            FROM dbo.lead l
            LEFT JOIN dbo.[user] u ON u.id = l.assigned_to_id
            WHERE CAST(
                SWITCHOFFSET(COALESCE(l.date_entry, l.created_at), '-05:00')
                AS date
            ) BETWEEN %s AND %s
            """,
            [date_from, date_to],
        )
        conversation_rows = _dict_rows(cursor)

        cursor.execute(
            """
            SELECT
                COUNT_BIG(*) AS total,
                SUM(CASE WHEN assigned_to_id IS NULL THEN 1 ELSE 0 END) AS no_agent,
                SUM(CASE WHEN date_last_message IS NULL THEN 1 ELSE 0 END) AS no_last_message,
                SUM(CASE WHEN id_chatwoot IS NULL THEN 1 ELSE 0 END) AS no_chatwoot,
                SUM(CASE WHEN contact_id IS NULL THEN 1 ELSE 0 END) AS no_contact
            FROM dbo.lead
            WHERE CAST(
                SWITCHOFFSET(COALESCE(date_entry, created_at), '-05:00')
                AS date
            ) BETWEEN %s AND %s
            """,
            [date_from, date_to],
        )
        data_quality = _one(cursor)

        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN lead_id IS NULL THEN 1 ELSE 0 END) AS events_without_lead,
                SUM(CASE WHEN start_time < '2000-01-01' THEN 1 ELSE 0 END) AS invalid_dates,
                COUNT_BIG(*) AS total_events
            FROM dbo.[event]
            WHERE (
                lead_id IN (
                    SELECT id
                    FROM dbo.lead
                    WHERE CAST(
                        SWITCHOFFSET(COALESCE(date_entry, created_at), '-05:00')
                        AS date
                    ) BETWEEN %s AND %s
                )
                OR (
                    lead_id IS NULL
                    AND CAST(SWITCHOFFSET(created_at, '-05:00') AS date)
                        BETWEEN %s AND %s
                )
            )
            """,
            [date_from, date_to, date_from, date_to],
        )
        data_quality.update(_one(cursor))

    conversation_rows = apply_visit_resolutions(conversation_rows)
    assessments = _assessment_map(conversation_rows)
    assignment_timelines = _load_assignment_timelines(conversation_rows)
    conversation_metrics = []
    for row in conversation_rows:
        analysis = _apply_contextual_assessment(
            analyze_chat_history(row["chat_history"]),
            assessments.get(
                (row["id"], conversation_hash(row["chat_history"]))
            ),
        )
        responsible = _responsible_at(
            assignment_timelines.get(row["id"], []),
            analysis["first_agent_response_at"],
            row["agent_id"],
            row["agent_name"],
        )
        waiting_attention = _waiting_attention(analysis, now)
        conversation_metrics.append(
            {
                "lead_id": row["id"],
                "cohort_date": row["cohort_date"],
                "first_visit_at": row["first_visit_at"],
                "agent_id": responsible["agent_id"],
                "agent_name": responsible["agent_name"],
                "current_agent_id": row["agent_id"],
                "current_agent_name": row["agent_name"],
                "assignment_changes": len(
                    assignment_timelines.get(row["id"], [])
                ),
                "media_gap_risk": possible_missing_media(
                    analysis["messages"]
                ),
                **analysis,
                **waiting_attention,
            }
        )
    data_quality["media_unobservable"] = sum(
        metric["media_gap_risk"] for metric in conversation_metrics
    )
    data_quality["with_assignment_changes"] = sum(
        metric["assignment_changes"] > 0 for metric in conversation_metrics
    )

    metrics_by_date = {}
    for metric in conversation_metrics:
        metrics_by_date.setdefault(metric["cohort_date"], []).append(metric)
    incoming_leads = build_daily_incoming(metrics_by_date, date_from, date_to)

    cohorts = []
    for daily_date in sorted(metrics_by_date, reverse=True):
        daily_metrics = metrics_by_date[daily_date]
        row = {
            "cohort_date": daily_date,
            "total": len(daily_metrics),
            "contacted_d1": sum(
                milestone_within_days(daily_date, metric["contacted_at"], 1)
                for metric in daily_metrics
            ),
            "bidirectional_d1": sum(
                milestone_within_days(daily_date, metric["bidirectional_at"], 1)
                for metric in daily_metrics
            ),
            "qualified_d1": sum(
                milestone_within_days(daily_date, metric["qualified_at"], 1)
                for metric in daily_metrics
            ),
            "qualified_d3": sum(
                milestone_within_days(daily_date, metric["qualified_at"], 3)
                for metric in daily_metrics
            ),
            "visit_intent_d7": sum(
                milestone_within_days(daily_date, metric["visit_intent_at"], 7)
                for metric in daily_metrics
            ),
            "visits_d7": sum(
                milestone_within_days(daily_date, metric["first_visit_at"], 7)
                for metric in daily_metrics
            ),
        }
        total = row["total"]
        for key in (
            "contacted_d1",
            "bidirectional_d1",
            "qualified_d1",
            "qualified_d3",
            "visit_intent_d7",
            "visits_d7",
        ):
            value = int(row[key])
            row[key] = value
            row[f"{key}_pct"] = round((value / total * 100), 1) if total else 0
        cohorts.append(row)

    selected_metrics = [
        metric
        for metric in conversation_metrics
        if cohort_date is None or metric["cohort_date"] == cohort_date
    ]
    selected_cohort = {
        "entered": len(selected_metrics),
        "unattended": sum(metric["unattended"] for metric in selected_metrics),
        "attention_overdue": sum(
            metric["attention_overdue"] for metric in selected_metrics
        ),
        "never_contacted_overdue": sum(
            metric["first_lead_at"] is not None
            and not metric["contacted"]
            and metric["attention_overdue"]
            for metric in selected_metrics
        ),
        "never_contacted": sum(
            metric["first_lead_at"] is not None and not metric["contacted"]
            for metric in selected_metrics
        ),
        "contacted": sum(metric["contacted"] for metric in selected_metrics),
        "bidirectional": sum(
            metric["bidirectional"] for metric in selected_metrics
        ),
        "context_analyzed": sum(
            metric["context_assessment"] is not None
            for metric in selected_metrics
        ),
        "context_pending": sum(
            metric["context_analysis_pending"]
            for metric in selected_metrics
        ),
        "qualified": sum(metric["qualified"] for metric in selected_metrics),
        "visit_intent": sum(
            metric["visit_intent"] for metric in selected_metrics
        ),
        "visit_registered": sum(
            metric["first_visit_at"] is not None for metric in selected_metrics
        ),
    }
    entered = selected_cohort["entered"]
    selected_cohort["context_unavailable"] = max(
        entered
        - selected_cohort["context_analyzed"]
        - selected_cohort["context_pending"],
        0,
    )
    for key in ("context_analyzed", "context_pending", "context_unavailable"):
        selected_cohort[f"{key}_pct"] = (
            round(selected_cohort[key] / entered * 100, 1) if entered else 0
        )
    for key in (
        "contacted",
        "bidirectional",
        "qualified",
        "visit_intent",
        "visit_registered",
    ):
        selected_cohort[f"{key}_pct"] = (
            round(selected_cohort[key] / entered * 100, 1) if entered else 0
        )

    agent_groups = {}
    for metric in conversation_metrics:
        group_key = metric["agent_id"] or "unassigned"
        group = agent_groups.setdefault(
            group_key,
            {
                "agent_id": metric["agent_id"],
                "agent_name": metric["agent_name"],
                "leads": 0,
                "contacted": 0,
                "bidirectional": 0,
                "qualified": 0,
                "unattended": 0,
            },
        )
        group["leads"] += 1
        group["contacted"] += int(metric["contacted"])
        group["bidirectional"] += int(metric["bidirectional"])
        group["qualified"] += int(metric["qualified"])
        group["unattended"] += int(metric["unattended"])
    for group in agent_groups.values():
        leads = group["leads"]
        for key in ("contacted", "bidirectional", "qualified", "unattended"):
            group[f"{key}_pct"] = (
                round(group[key] / leads * 100, 1) if leads else 0
            )
        group["bidirectional_from_contacted_pct"] = (
            round(group["bidirectional"] / group["contacted"] * 100, 1)
            if group["contacted"]
            else None
        )
    agent_load = sorted(
        agent_groups.values(),
        key=lambda row: (-row["unattended"], -row["leads"], row["agent_name"]),
    )[:8]
    comparable_conversion_rates = [
        row["bidirectional_from_contacted_pct"]
        for row in agent_load
        if row["bidirectional_from_contacted_pct"] is not None
    ]
    contact_rates = [row["contacted_pct"] for row in agent_load]
    highest_contact_rate = max(contact_rates) if contact_rates else None
    lowest_contact_rate = min(contact_rates) if contact_rates else None
    highest_conversion_rate = (
        max(comparable_conversion_rates) if comparable_conversion_rates else None
    )
    lowest_conversion_rate = (
        min(comparable_conversion_rates) if comparable_conversion_rates else None
    )
    for row in agent_load:
        contact_rate = row["contacted_pct"]
        if contact_rate == highest_contact_rate:
            row["contact_tone"] = "highest"
        elif contact_rate == lowest_contact_rate:
            row["contact_tone"] = "lowest"
        else:
            row["contact_tone"] = "middle"
        rate = row["bidirectional_from_contacted_pct"]
        if rate is None:
            row["conversion_tone"] = "neutral"
        elif rate == highest_conversion_rate:
            row["conversion_tone"] = "highest"
        elif rate == lowest_conversion_rate:
            row["conversion_tone"] = "lowest"
        else:
            row["conversion_tone"] = "middle"

    data_quality.update(
        {
            "no_chat_history": sum(
                metric["is_null"] for metric in conversation_metrics
            ),
            "empty_chat_history": sum(
                metric["empty_history"] for metric in conversation_metrics
            ),
            "invalid_chat_history": sum(
                not metric["valid_json"] for metric in conversation_metrics
            ),
            "messages_without_valid_timestamp": sum(
                metric["raw_useful_message_count"] > 0
                and metric["total_messages"] == 0
                for metric in conversation_metrics
            ),
            "unknown_senders": sum(
                metric["unknown_senders"] > 0 for metric in conversation_metrics
            ),
            "pending_context_analysis": sum(
                metric["context_analysis_pending"]
                for metric in conversation_metrics
            ),
        }
    )

    return {
        "generated_at": now,
        "date_from": date_from,
        "date_to": date_to,
        "cohort_date": cohort_date,
        "funnel_scope_from": cohort_date or date_from,
        "funnel_scope_to": cohort_date or date_to,
        "overview": overview,
        "incoming_leads": incoming_leads,
        "cohorts": cohorts,
        "selected_cohort": selected_cohort,
        "agent_load": agent_load,
        "data_quality": data_quality,
    }


def normalized_period(date_from_raw, date_to_raw):
    today = timezone.localdate()
    default_from = today - timedelta(days=13)
    try:
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else default_from
    except ValueError:
        date_from = default_from
    try:
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else today
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    if (date_to - date_from).days > 90:
        date_from = date_to - timedelta(days=90)
    return date_from, date_to
