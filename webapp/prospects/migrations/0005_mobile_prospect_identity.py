from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('prospects', '0004_propertyprospect_photo_optional')]

    operations = [
        migrations.AlterField(
            model_name='propertyprospect',
            name='agent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prospects', to='intelligence.user', verbose_name='Agente'),
        ),
        migrations.CreateModel(
            name='MobileProspectUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('propify_user_id', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='MobileProspectSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(db_index=True, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='prospects.mobileprospectuser')),
            ],
        ),
        migrations.AddField(
            model_name='propertyprospect',
            name='mobile_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prospects', to='prospects.mobileprospectuser', verbose_name='Usuario móvil'),
        ),
        migrations.AddField(
            model_name='propertyprospect',
            name='captured_by_username',
            field=models.CharField(blank=True, db_index=True, max_length=150, verbose_name='Usuario que realizó la captura'),
        ),
    ]
