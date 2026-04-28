# Generated manually para compatibilidad con Django 5.0.6

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0009_user_first_name_user_last_login_user_last_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(default='', max_length=50, unique=True, verbose_name='Nombre de usuario'),
        ),
    ]
