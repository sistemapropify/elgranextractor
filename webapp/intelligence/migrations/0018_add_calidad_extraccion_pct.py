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
                migrations.RunSQL(
                    sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [calidad_extraccion_pct] FLOAT NULL",
                    reverse_sql="ALTER TABLE [intelligence_aiconsumptionlog] ALTER COLUMN [calidad_extraccion_pct] FLOAT NOT NULL",
                ),
            ],
        ),
    ]
