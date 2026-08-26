from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("n8n_bridge", "0004_propertybotconfiguration_office_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertybotconfiguration",
            name="captacion_delay_seconds",
            field=models.PositiveIntegerField(
                choices=[
                    (60, "1 minuto"),
                    (300, "5 minutos"),
                    (900, "15 minutos"),
                    (1800, "30 minutos"),
                    (3600, "1 hora"),
                    (7200, "2 horas"),
                ],
                default=60,
            ),
        ),
    ]
