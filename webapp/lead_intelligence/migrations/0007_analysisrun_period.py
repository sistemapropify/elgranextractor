from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lead_intelligence", "0006_analysisrunstep"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisrun",
            name="date_from",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="analysisrun",
            name="date_to",
            field=models.DateField(blank=True, null=True),
        ),
    ]
