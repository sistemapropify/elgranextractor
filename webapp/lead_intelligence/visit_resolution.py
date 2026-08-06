from __future__ import annotations

import logging
from decimal import Decimal

from django.db import DatabaseError, connections
from django.utils import timezone

from .models import LeadEventResolution


logger = logging.getLogger(__name__)

VISIT_RESOLUTION_VERSION = "visit-link-v1"
AUTO_RESOLUTION_THRESHOLD = Decimal("0.9000")


VISIT_RESOLUTION_SQL = r"""
WITH visit_events AS (
    SELECT
        e.id AS event_id,
        e.lead_id AS direct_lead_id,
        e.contact_id AS event_contact_id,
        e.property_id AS event_property_id,
        e.created_at AS event_created_at,
        e.start_time AS event_scheduled_at,
        LOWER(LTRIM(RTRIM(COALESCE(
            NULLIF(CONCAT(ec.first_name, ' ', ec.last_name), ' '),
            ec.business_name,
            ''
        )))) AS event_contact_name,
        RIGHT(
            REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                COALESCE(ec.phone, ''), '+', ''
            ), ' ', ''), '-', ''), '(', ''), ')', ''),
            9
        ) AS event_phone
    FROM dbo.[event] e
    INNER JOIN dbo.event_type et ON et.id = e.event_type_id
    LEFT JOIN dbo.contact ec ON ec.id = e.contact_id
    WHERE LOWER(LTRIM(RTRIM(et.name))) = 'visita'
),
candidate_evidence AS (
    SELECT
        visit.event_id,
        candidate.id AS candidate_lead_id,
        COALESCE(candidate.date_entry, candidate.created_at) AS lead_entered_at,
        CASE
            WHEN visit.event_contact_id IS NOT NULL
             AND candidate.contact_id = visit.event_contact_id
            THEN 1 ELSE 0
        END AS contact_id_match,
        CASE
            WHEN LEN(visit.event_phone) = 9
             AND LEN(candidate_contact_data.candidate_phone) = 9
             AND visit.event_phone = candidate_contact_data.candidate_phone
            THEN 1 ELSE 0
        END AS phone_match,
        CASE
            WHEN visit.event_property_id IS NOT NULL AND EXISTS (
                SELECT 1
                FROM dbo.lead_properties lp
                WHERE lp.lead_id = candidate.id
                  AND lp.property_id = visit.event_property_id
            )
            THEN 1 ELSE 0
        END AS property_match,
        CASE
            WHEN visit.event_contact_name <> ''
             AND visit.event_contact_name = candidate_contact_data.candidate_name
            THEN 1 ELSE 0
        END AS name_match
    FROM visit_events visit
    INNER JOIN dbo.lead candidate
        ON visit.direct_lead_id IS NULL
       AND COALESCE(candidate.date_entry, candidate.created_at)
           <= visit.event_created_at
    LEFT JOIN dbo.contact candidate_contact
        ON candidate_contact.id = candidate.contact_id
    CROSS APPLY (
        SELECT
            LOWER(LTRIM(RTRIM(COALESCE(
                NULLIF(CONCAT(
                    candidate_contact.first_name,
                    ' ',
                    candidate_contact.last_name
                ), ' '),
                candidate_contact.business_name,
                ''
            )))) AS candidate_name,
            RIGHT(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(candidate_contact.phone, ''), '+', ''
                ), ' ', ''), '-', ''), '(', ''), ')', ''),
                9
            ) AS candidate_phone
    ) candidate_contact_data
    WHERE (
        visit.event_contact_id IS NOT NULL
        AND candidate.contact_id = visit.event_contact_id
    ) OR (
        LEN(visit.event_phone) = 9
        AND LEN(candidate_contact_data.candidate_phone) = 9
        AND visit.event_phone = candidate_contact_data.candidate_phone
    )
),
scored_candidates AS (
    SELECT
        evidence.*,
        CAST(
            CASE
                WHEN contact_id_match = 1 AND property_match = 1 THEN 0.9800
                WHEN contact_id_match = 1 AND name_match = 1 THEN 0.9400
                WHEN contact_id_match = 1 THEN 0.9200
                WHEN phone_match = 1 AND property_match = 1
                 AND name_match = 1 THEN 0.9300
                WHEN phone_match = 1 AND property_match = 1 THEN 0.9000
                WHEN phone_match = 1 AND name_match = 1 THEN 0.8600
                WHEN phone_match = 1 THEN 0.8200
                ELSE 0.0000
            END AS decimal(5, 4)
        ) AS confidence,
        CASE
            WHEN contact_id_match = 1 AND property_match = 1
                THEN 'contact_property'
            WHEN contact_id_match = 1 AND name_match = 1
                THEN 'contact_name'
            WHEN contact_id_match = 1 THEN 'contact_id'
            WHEN phone_match = 1 AND property_match = 1
                THEN 'phone_property'
            WHEN phone_match = 1 AND name_match = 1
                THEN 'phone_name'
            WHEN phone_match = 1 THEN 'phone'
            ELSE 'unresolved'
        END AS resolution_method
    FROM candidate_evidence evidence
),
ranked_candidates AS (
    SELECT
        scored.*,
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY
                confidence DESC,
                lead_entered_at DESC,
                candidate_lead_id DESC
        ) AS candidate_rank,
        COUNT_BIG(*) OVER (
            PARTITION BY event_id, confidence
        ) AS confidence_ties,
        COUNT_BIG(*) OVER (
            PARTITION BY event_id
        ) AS candidate_count
    FROM scored_candidates scored
)
SELECT
    visit.event_id,
    CASE
        WHEN visit.direct_lead_id IS NOT NULL THEN visit.direct_lead_id
        WHEN ranked.confidence >= 0.9000
         AND ranked.confidence_ties = 1 THEN ranked.candidate_lead_id
        ELSE NULL
    END AS resolved_lead_id,
    visit.event_contact_id,
    visit.event_property_id,
    visit.event_created_at,
    visit.event_scheduled_at,
    CASE
        WHEN visit.direct_lead_id IS NOT NULL THEN 'direct_lead_id'
        WHEN ranked.confidence >= 0.9000
         AND ranked.confidence_ties = 1 THEN ranked.resolution_method
        WHEN ranked.candidate_lead_id IS NOT NULL THEN 'manual_review'
        ELSE 'unresolved'
    END AS resolution_method,
    CAST(
        CASE
            WHEN visit.direct_lead_id IS NOT NULL THEN 1.0000
            ELSE COALESCE(ranked.confidence, 0.0000)
        END AS decimal(5, 4)
    ) AS confidence,
    CASE
        WHEN visit.direct_lead_id IS NOT NULL THEN 'confirmed'
        WHEN ranked.confidence >= 0.9000
         AND ranked.confidence_ties = 1 THEN 'confirmed'
        WHEN ranked.candidate_lead_id IS NOT NULL THEN 'manual_review'
        ELSE 'unresolved'
    END AS resolution_status,
    COALESCE(ranked.candidate_count, 0) AS candidate_count,
    COALESCE(ranked.confidence_ties, 0) AS confidence_ties,
    COALESCE(ranked.contact_id_match, 0) AS contact_id_match,
    COALESCE(ranked.phone_match, 0) AS phone_match,
    COALESCE(ranked.property_match, 0) AS property_match,
    COALESCE(ranked.name_match, 0) AS name_match,
    ranked.candidate_lead_id AS best_candidate_lead_id
FROM visit_events visit
LEFT JOIN ranked_candidates ranked
    ON ranked.event_id = visit.event_id
   AND ranked.candidate_rank = 1
"""


def _dict_rows(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_visit_resolutions():
    """Resolve every CRM visit using SELECT-only queries."""
    with connections["propifai"].cursor() as cursor:
        cursor.execute(VISIT_RESOLUTION_SQL)
        return _dict_rows(cursor)


def _evidence(row):
    return {
        "contact_id_match": bool(row.get("contact_id_match")),
        "phone_match": bool(row.get("phone_match")),
        "property_match": bool(row.get("property_match")),
        "name_match": bool(row.get("name_match")),
        "candidate_count": int(row.get("candidate_count") or 0),
        "confidence_ties": int(row.get("confidence_ties") or 0),
        "best_candidate_lead_id": row.get("best_candidate_lead_id"),
    }


def persist_visit_resolutions(rows):
    """Persist the audit trail in Prometeo's default database."""
    rows = list(rows)
    if not rows:
        return
    event_ids = [int(row["event_id"]) for row in rows]
    existing = {
        item.source_event_id: item
        for item in LeadEventResolution.objects.using("default").filter(
            source_event_id__in=event_ids,
            resolver_version=VISIT_RESOLUTION_VERSION,
        )
    }
    now = timezone.now()
    to_create = []
    to_update = []
    fields = (
        "source_lead_id",
        "source_contact_id",
        "source_property_id",
        "event_created_at",
        "event_scheduled_at",
        "resolution_method",
        "resolution_status",
        "confidence",
        "candidate_count",
        "evidence",
        "resolved_at",
    )
    for row in rows:
        values = {
            "source_lead_id": row.get("resolved_lead_id"),
            "source_contact_id": row.get("event_contact_id"),
            "source_property_id": row.get("event_property_id"),
            "event_created_at": row.get("event_created_at"),
            "event_scheduled_at": row.get("event_scheduled_at"),
            "resolution_method": row["resolution_method"],
            "resolution_status": row["resolution_status"],
            "confidence": row.get("confidence") or Decimal("0"),
            "candidate_count": int(row.get("candidate_count") or 0),
            "evidence": _evidence(row),
            "resolved_at": now,
        }
        event_id = int(row["event_id"])
        item = existing.get(event_id)
        if item is None:
            to_create.append(
                LeadEventResolution(
                    source_event_id=event_id,
                    resolver_version=VISIT_RESOLUTION_VERSION,
                    **values,
                )
            )
            continue
        changed = False
        for field, value in values.items():
            if getattr(item, field) != value:
                setattr(item, field, value)
                changed = True
        if changed:
            to_update.append(item)
    if to_create:
        LeadEventResolution.objects.using("default").bulk_create(to_create)
    if to_update:
        LeadEventResolution.objects.using("default").bulk_update(
            to_update,
            fields,
        )


def resolve_visits_for_leads(lead_ids, persist=True):
    selected_ids = {int(lead_id) for lead_id in lead_ids if lead_id is not None}
    if not selected_ids:
        return []
    rows = [
        row
        for row in load_visit_resolutions()
        if row.get("resolved_lead_id") in selected_ids
        and row.get("resolution_status") == LeadEventResolution.Status.CONFIRMED
    ]
    if persist:
        try:
            persist_visit_resolutions(rows)
        except DatabaseError:
            logger.exception("No se pudo persistir la resolución de visitas")
    return rows


def apply_visit_resolutions(lead_rows, persist=True):
    lead_rows = list(lead_rows)
    resolutions = resolve_visits_for_leads(
        (row.get("id") for row in lead_rows),
        persist=persist,
    )
    first_by_lead = {}
    for resolution in resolutions:
        lead_id = int(resolution["resolved_lead_id"])
        registered_at = resolution.get("event_created_at")
        if registered_at is None:
            continue
        current = first_by_lead.get(lead_id)
        if current is None or registered_at < current:
            first_by_lead[lead_id] = registered_at
    for row in lead_rows:
        row["first_visit_at"] = first_by_lead.get(int(row["id"]))
    return lead_rows
