from django.db import migrations, models
import django.db.models.deletion


def enable_initial_supervisor(apps, schema_editor):
    User = apps.get_model('prospects', 'MobileProspectUser')
    User.objects.filter(username__iexact='adminpropify').update(can_view_crm_alerts=True)


class Migration(migrations.Migration):
    dependencies = [('prospects', '0006_mobileappversion')]
    operations = [
        migrations.AddField(model_name='mobileprospectuser', name='can_view_crm_alerts', field=models.BooleanField(default=False, verbose_name='Supervisor de alertas CRM')),
        migrations.CreateModel(name='CrmVisitIntentAlert', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('source_lead_id', models.BigIntegerField(db_index=True)), ('agent_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
            ('agent_name', models.CharField(blank=True, max_length=200)), ('contact_name', models.CharField(blank=True, max_length=200)),
            ('phone', models.CharField(blank=True, max_length=50)), ('property_id', models.BigIntegerField(blank=True, null=True)),
            ('property_code', models.CharField(blank=True, max_length=100)), ('property_title', models.CharField(blank=True, max_length=300)),
            ('evidence', models.JSONField(default=list)), ('detected_at', models.DateTimeField(db_index=True)),
            ('responded_at', models.DateTimeField(blank=True, db_index=True, null=True)),
            ('status', models.CharField(choices=[('pending','Pendiente'),('follow_up','Seguimiento'),('closed','Cerrada')], db_index=True, default='pending', max_length=20)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'ordering':['-detected_at']}),
        migrations.AddConstraint(model_name='crmvisitintentalert', constraint=models.UniqueConstraint(fields=('source_lead_id','detected_at'), name='unique_crm_visit_intent_alert')),
        migrations.CreateModel(name='MobileNotificationDevice', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('registration_id', models.CharField(max_length=512, unique=True)),
            ('target_type', models.CharField(choices=[('fid','Firebase Installation ID'),('token','Token heredado')], default='fid', max_length=10)),
            ('device_name', models.CharField(blank=True, max_length=200)),
            ('active', models.BooleanField(db_index=True, default=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_devices', to='prospects.mobileprospectuser')),
        ]),
        migrations.RunPython(enable_initial_supervisor, migrations.RunPython.noop),
    ]
