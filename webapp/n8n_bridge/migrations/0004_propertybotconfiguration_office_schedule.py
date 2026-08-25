from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("n8n_bridge", "0003_propertybotconfiguration_message_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertybotconfiguration",
            name="office_start_time",
            field=models.TimeField(default="09:00"),
        ),
        migrations.AddField(
            model_name="propertybotconfiguration",
            name="office_end_time",
            field=models.TimeField(default="18:00"),
        ),
        migrations.AddField(
            model_name="propertybotconfiguration",
            name="advisor_message_in_hours",
            field=models.CharField(
                default=(
                    "Un asesor podrá indicarle con exactitud el estado de "
                    "{property_reference} y absolver todas sus consultas."
                ),
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="propertybotconfiguration",
            name="advisor_message_out_of_hours",
            field=models.CharField(
                default=(
                    "Un asesor podrá indicarle con exactitud el estado de "
                    "{property_reference} y absolver todas sus consultas en horario de atención."
                ),
                max_length=500,
            ),
        ),
    ]
