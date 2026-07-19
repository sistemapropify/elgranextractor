"""
Add calidad_extraccion_pct field to AIConsumptionLog and make it nullable.

This field was previously added directly to the database as NOT NULL with no default,
but the Django model didn't know about it. This migration:
1. Registers the field in Django's schema tracking (state_operations)
2. Alters the column to allow NULL values (database_operations)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0017_add_ai_consumption_log'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='aiconsumptionlog',
                    name='calidad_extraccion_pct',
                    field=models.FloatField(
                        blank=True,
                        null=True,
                        verbose_name='Calidad de extracción (%)',
                    ),
                ),
            ],
            database_operations=[
                # Crear columna si no existe (para test database donde la columna no está en BD)
                migrations.RunSQL(
                    sql="""
                        IF NOT EXISTS (
                            SELECT 1 FROM sys.columns
                            WHERE object_id = OBJECT_ID(N'[intelligence_aiconsumptionlog]')
                            AND name = 'calidad_extraccion_pct'
                        )
                        ALTER TABLE [intelligence_aiconsumptionlog]
                        ADD [calidad_extraccion_pct] FLOAT NULL
                    """,
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] DROP COLUMN [calidad_extraccion_pct]",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [calidad_extraccion_pct] FLOAT NULL",
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [calidad_extraccion_pct] FLOAT NOT NULL",
                ),
            ],
        ),
    ]
