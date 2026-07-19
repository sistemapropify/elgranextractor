"""
Add skill_name and campos_faltantes fields to AIConsumptionLog.

These fields were previously added directly to the database as NOT NULL with no default,
but the Django model didn't know about them. This migration:
1. Registers the fields in Django's schema tracking (state_operations)
2. Alters the columns to allow NULL values (database_operations)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0019_add_input_summary'),
    ]

    operations = [
        # --- skill_name ---
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='aiconsumptionlog',
                    name='skill_name',
                    field=models.CharField(
                        blank=True, default=None, max_length=200,
                        null=True, verbose_name='Nombre del skill ejecutado',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        IF NOT EXISTS (
                            SELECT 1 FROM sys.columns
                            WHERE object_id = OBJECT_ID(N'[intelligence_aiconsumptionlog]')
                            AND name = 'skill_name'
                        )
                        ALTER TABLE [intelligence_aiconsumptionlog]
                        ADD [skill_name] NVARCHAR(200) NULL
                    """,
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] DROP COLUMN [skill_name]",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [skill_name] NVARCHAR(200) NULL",
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [skill_name] NVARCHAR(200) NOT NULL",
                ),
            ],
        ),
        # --- campos_faltantes ---
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='aiconsumptionlog',
                    name='campos_faltantes',
                    field=models.TextField(
                        blank=True, default=None,
                        null=True, verbose_name='Campos faltantes detectados',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        IF NOT EXISTS (
                            SELECT 1 FROM sys.columns
                            WHERE object_id = OBJECT_ID(N'[intelligence_aiconsumptionlog]')
                            AND name = 'campos_faltantes'
                        )
                        ALTER TABLE [intelligence_aiconsumptionlog]
                        ADD [campos_faltantes] NVARCHAR(MAX) NULL
                    """,
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] DROP COLUMN [campos_faltantes]",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [campos_faltantes] NVARCHAR(MAX) NULL",
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [campos_faltantes] NVARCHAR(MAX) NOT NULL",
                ),
            ],
        ),
    ]
