from django.db import migrations, models

from n8n_bridge.models import default_message_templates


class Migration(migrations.Migration):

    dependencies = [
        ("n8n_bridge", "0002_propertybotinitialresponse_phone_contact_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertybotconfiguration",
            name="message_templates",
            field=models.JSONField(default=default_message_templates),
        ),
    ]
