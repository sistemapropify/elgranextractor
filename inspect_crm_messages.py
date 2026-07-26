import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

import django

django.setup()

from django.db import connections


with connections["propifai"].cursor() as cursor:
    cursor.execute(
        """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
          AND (
            LOWER(TABLE_NAME) LIKE '%message%'
            OR LOWER(TABLE_NAME) LIKE '%conversation%'
            OR LOWER(TABLE_NAME) LIKE '%chat%'
          )
        ORDER BY TABLE_NAME
        """
    )
    print("MESSAGE_TABLES", cursor.fetchall())

    for table_name in ("lead", "contact", "user_chatwoot"):
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            [table_name],
        )
        print("COLUMNS", table_name, cursor.fetchall())

    cursor.execute(
        """
        SELECT l.id, l.id_chatwoot, l.created_at, l.date_last_message,
               l.user_last_message, l.last_message_text, l.lead_status_id,
               c.id, c.phone, c.first_name, c.last_name
        FROM lead l
        INNER JOIN contact c ON c.id = l.contact_id
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(c.phone, '+', ''), ' ', ''), '-', ''), '(', '')
              LIKE %s
        ORDER BY l.created_at DESC
        """,
        ["%955400058"],
    )
    print("TARGET_LEAD", cursor.fetchall())

    cursor.execute(
        """
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE LOWER(COLUMN_NAME) LIKE '%chatwoot%'
           OR LOWER(COLUMN_NAME) LIKE '%base_url%'
           OR LOWER(COLUMN_NAME) LIKE '%account_id%'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
    )
    print("CHATWOOT_CONFIG_COLUMNS", cursor.fetchall())
