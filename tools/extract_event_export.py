import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

import django

django.setup()

from django.db import connections


OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "event_export"
OUTPUT.mkdir(parents=True, exist_ok=True)


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def dict_rows(cursor):
    columns = [column[0] for column in cursor.description]
    return [
        {column: json_value(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]


with connections["propifai"].cursor() as cursor:
    cursor.execute(
        """
        SELECT
            e.id,
            e.created_at,
            e.updated_at,
            e.code,
            e.title,
            e.description,
            e.tracing,
            e.start_time,
            e.end_time,
            e.status,
            e.is_active,
            e.assigned_agent_id,
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONCAT(aa.first_name, ' ', aa.last_name))), ''),
                aa.username
            ) AS assigned_agent_name,
            e.contact_id,
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONCAT(c.first_name, ' ', c.last_name))), ''),
                c.business_name
            ) AS contact_name,
            c.phone AS contact_phone,
            c.email AS contact_email,
            e.created_by_id,
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONCAT(cu.first_name, ' ', cu.last_name))), ''),
                cu.username
            ) AS created_by_name,
            e.event_type_id,
            et.name AS event_type_name,
            e.property_id,
            p.code AS property_code,
            p.title AS property_title,
            e.updated_by_id,
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONCAT(uu.first_name, ' ', uu.last_name))), ''),
                uu.username
            ) AS updated_by_name,
            e.lead_id,
            COALESCE(
                NULLIF(LTRIM(RTRIM(CONCAT(lc.first_name, ' ', lc.last_name))), ''),
                lc.business_name,
                l.username
            ) AS lead_contact_name,
            lc.phone AS lead_contact_phone,
            l.id_chatwoot AS lead_chatwoot_id,
            e.match_id,
            CONCAT(
                COALESCE(m.match_status, 'Sin estado'),
                CASE WHEN mc.id IS NOT NULL
                     THEN CONCAT(' | ', COALESCE(
                         NULLIF(LTRIM(RTRIM(CONCAT(mc.first_name, ' ', mc.last_name))), ''),
                         mc.business_name
                     ))
                     ELSE '' END,
                CASE WHEN mp.id IS NOT NULL
                     THEN CONCAT(' | ', COALESCE(mp.code, ''), ' ', COALESCE(mp.title, ''))
                     ELSE '' END
            ) AS match_description,
            e.proposal_id,
            CONCAT(
                COALESCE(pr.status, 'Sin estado'),
                CASE WHEN pc.id IS NOT NULL
                     THEN CONCAT(' | ', COALESCE(
                         NULLIF(LTRIM(RTRIM(CONCAT(pc.first_name, ' ', pc.last_name))), ''),
                         pc.business_name
                     ))
                     ELSE '' END,
                CASE WHEN pp.id IS NOT NULL
                     THEN CONCAT(' | ', COALESCE(pp.code, ''), ' ', COALESCE(pp.title, ''))
                     ELSE '' END,
                CASE WHEN pr.amount IS NOT NULL
                     THEN CONCAT(' | Monto: ', CONVERT(varchar(40), pr.amount))
                     ELSE '' END
            ) AS proposal_description,
            e.completed
        FROM dbo.[event] e
        LEFT JOIN dbo.[user] aa ON aa.id = e.assigned_agent_id
        LEFT JOIN dbo.contact c ON c.id = e.contact_id
        LEFT JOIN dbo.[user] cu ON cu.id = e.created_by_id
        LEFT JOIN dbo.event_type et ON et.id = e.event_type_id
        LEFT JOIN dbo.property p ON p.id = e.property_id
        LEFT JOIN dbo.[user] uu ON uu.id = e.updated_by_id
        LEFT JOIN dbo.lead l ON l.id = e.lead_id
        LEFT JOIN dbo.contact lc ON lc.id = l.contact_id
        LEFT JOIN dbo.[match] m ON m.id = e.match_id
        LEFT JOIN dbo.lead ml ON ml.id = m.lead_id
        LEFT JOIN dbo.contact mc ON mc.id = ml.contact_id
        LEFT JOIN dbo.property mp ON mp.id = m.property_id
        LEFT JOIN dbo.proposal pr ON pr.id = e.proposal_id
        LEFT JOIN dbo.lead pl ON pl.id = pr.lead_id
        LEFT JOIN dbo.contact pc ON pc.id = pl.contact_id
        LEFT JOIN dbo.property pp ON pp.id = pr.property_id
        ORDER BY e.id
        """
    )
    events = dict_rows(cursor)

    cursor.execute(
        """
        SELECT
            COUNT_BIG(*) AS total_events,
            SUM(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END) AS with_lead,
            SUM(CASE WHEN lead_id IS NULL THEN 1 ELSE 0 END) AS without_lead,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS not_completed,
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive
        FROM dbo.[event]
        """
    )
    summary = dict_rows(cursor)[0]

    cursor.execute(
        """
        SELECT
            COALESCE(et.name, 'Sin tipo') AS event_type,
            COUNT_BIG(*) AS total,
            SUM(CASE WHEN e.lead_id IS NOT NULL THEN 1 ELSE 0 END) AS with_lead,
            SUM(CASE WHEN e.lead_id IS NULL THEN 1 ELSE 0 END) AS without_lead
        FROM dbo.[event] e
        LEFT JOIN dbo.event_type et ON et.id = e.event_type_id
        GROUP BY COALESCE(et.name, 'Sin tipo')
        ORDER BY total DESC, event_type
        """
    )
    by_type = dict_rows(cursor)

    cursor.execute(
        """
        SELECT
            COALESCE(status, 'Sin estado') AS status,
            COUNT_BIG(*) AS total,
            SUM(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END) AS with_lead,
            SUM(CASE WHEN lead_id IS NULL THEN 1 ELSE 0 END) AS without_lead
        FROM dbo.[event]
        GROUP BY COALESCE(status, 'Sin estado')
        ORDER BY total DESC, status
        """
    )
    by_status = dict_rows(cursor)

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "summary": summary,
    "by_type": by_type,
    "by_status": by_status,
    "events": events,
}
(OUTPUT / "event_export_data.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "rows": len(events),
            "summary": summary,
            "types": len(by_type),
            "statuses": len(by_status),
        },
        ensure_ascii=False,
    )
)
