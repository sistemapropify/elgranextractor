import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

import django

django.setup()

from django.db import connections


OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "event_export"
OUTPUT.mkdir(parents=True, exist_ok=True)

with connections["propifai"].cursor() as cursor:
    cursor.execute(
        """
        SELECT
            c.ORDINAL_POSITION,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_SCHEMA = 'dbo' AND c.TABLE_NAME = 'event'
        ORDER BY c.ORDINAL_POSITION
        """
    )
    columns = [
        {
            "position": row[0],
            "name": row[1],
            "type": row[2],
            "max_length": row[3],
            "nullable": row[4],
        }
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT
            fk.name AS constraint_name,
            pc.name AS source_column,
            rt.name AS target_table,
            rc.name AS target_column
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc
          ON fkc.constraint_object_id = fk.object_id
        JOIN sys.tables pt ON pt.object_id = fk.parent_object_id
        JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
        JOIN sys.columns pc
          ON pc.object_id = pt.object_id
         AND pc.column_id = fkc.parent_column_id
        JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id
        JOIN sys.columns rc
          ON rc.object_id = rt.object_id
         AND rc.column_id = fkc.referenced_column_id
        WHERE ps.name = 'dbo' AND pt.name = 'event'
        ORDER BY pc.column_id
        """
    )
    foreign_keys = [
        {
            "constraint": row[0],
            "source_column": row[1],
            "target_table": row[2],
            "target_column": row[3],
        }
        for row in cursor.fetchall()
    ]

    related_columns = {}
    for fk in foreign_keys:
        table = fk["target_table"]
        cursor.execute(
            """
            SELECT ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            [table],
        )
        related_columns[table] = [
            {"position": row[0], "name": row[1], "type": row[2]}
            for row in cursor.fetchall()
        ]

    cursor.execute("SELECT COUNT_BIG(*) FROM dbo.[event]")
    row_count = int(cursor.fetchone()[0])

payload = {
    "row_count": row_count,
    "columns": columns,
    "foreign_keys": foreign_keys,
    "related_columns": related_columns,
}
(OUTPUT / "event_schema.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(json.dumps(payload, ensure_ascii=False))
