"""Initial migration for canvas app (PropFlow Visual Canvas)."""
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CardTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('campos', models.JSONField(default=list)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='Lienzo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200)),
                ('descripcion', models.TextField(blank=True)),
                ('estado', models.CharField(choices=[('activo', 'Activo'), ('archivado', 'Archivado')], default='activo', max_length=20)),
                ('snapshot', models.JSONField(default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('card_template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='canvas.cardtemplate')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-actualizado_en'],
            },
        ),
        migrations.CreateModel(
            name='NotaLienzo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contenido', models.TextField()),
                ('color', models.CharField(default='#2a2a2a', max_length=20)),
                ('x', models.IntegerField(default=100)),
                ('y', models.IntegerField(default=100)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('lienzo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notas', to='canvas.lienzo')),
            ],
        ),
    ]
