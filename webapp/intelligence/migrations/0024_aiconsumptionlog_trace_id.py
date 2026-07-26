from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0023_alter_systemtrace_status_needs_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiconsumptionlog',
            name='trace_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                max_length=64,
                verbose_name='Traza de la consulta',
            ),
        ),
    ]
