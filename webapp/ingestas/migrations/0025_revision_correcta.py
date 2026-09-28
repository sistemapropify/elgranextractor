"""Marca humana 'revisada y correcta' en la revision de calidad."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('ingestas', '0024_revision_ia_alerta')]
    operations = [
        migrations.AddField(
            model_name='revisionpropiedadscraping',
            name='correcta',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='revisionpropiedadscraping',
            name='corregida_en',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
