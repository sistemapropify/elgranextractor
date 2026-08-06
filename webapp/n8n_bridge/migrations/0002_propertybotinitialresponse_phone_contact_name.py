from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("n8n_bridge", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertybotinitialresponse",
            name="contact_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="propertybotinitialresponse",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
