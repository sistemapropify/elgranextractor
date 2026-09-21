import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('ingestas', '0020_propiedadescompetencia_precision_ubicacion')]
    operations = [migrations.CreateModel(
        name='ScrapingVerification',
        fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('execution_token', models.UUIDField()),
            ('expires_at', models.DateTimeField()),
            ('state', models.CharField(max_length=16, default='waiting')),
            ('screenshot', models.TextField(default='')),
            ('answer', models.CharField(max_length=16, default='')),
            ('run', models.ForeignKey(to='ingestas.ejecucionportal', on_delete=django.db.models.deletion.CASCADE)),
        ],
        options={'db_table': 'scraping_verifications'},
    )]
