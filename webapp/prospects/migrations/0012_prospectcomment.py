import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0011_alter_propertyprospect_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProspectComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('author_username', models.CharField(max_length=150, verbose_name='Autor (username Propify)')),
                ('text', models.TextField(verbose_name='Comentario')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')),
                ('prospect', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='prospects.propertyprospect', verbose_name='Prospección')),
            ],
            options={
                'verbose_name': 'Comentario de prospección',
                'verbose_name_plural': 'Comentarios de prospección',
                'ordering': ['created_at'],
            },
        ),
    ]
