"""
Add input_summary field to AIConsumptionLog and make it nullable.

This field was previously added directly to the database as NOT NULL with no default,
but the Django model didn't know about it. This migration:
1. Registers the field in Django's schema tracking (state_operations)
2. Alters the column to allow NULL values (database_operations)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0018_add_calidad_extraccion_pct'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='aiconsumptionlog',
                    name='input_summary',
                    field=models.TextField(
                        blank=True,
                        default=None,
                        null=True,
                        verbose_name='Resumen del prompt de entrada',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        IF NOT EXISTS (
                            SELECT 1 FROM sys.columns
                            WHERE object_id = OBJECT_ID(N'[intelligence_aiconsumptionlog]')
                            AND name = 'input_summary'
                        )
                        ALTER TABLE [intelligence_aiconsumptionlog]
                        ADD [input_summary] NVARCHAR(MAX) NULL
                    """,
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] DROP COLUMN [input_summary]",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [input_summary] NVARCHAR(MAX) NULL",
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [input_summary] NVARCHAR(MAX) NOT NULL",
                ),
            ],
        ),
    ]
