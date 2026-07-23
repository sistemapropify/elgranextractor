from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0022_alter_systemtrace_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemtrace',
            name='status',
            field=models.CharField(
                choices=[
                    ('started', 'Iniciada'),
                    ('completed', 'Completada'),
                    ('completed_degraded', 'Completada con fallback'),
                    ('completed_empty', 'Completada sin resultados'),
                    ('needs_review', 'Requiere revisión'),
                    ('failed', 'Fallida'),
                    ('timeout', 'Timeout'),
                    ('blocked', 'Bloqueada por guardrail'),
                ],
                db_index=True,
                default='started',
                max_length=30,
            ),
        ),
    ]
