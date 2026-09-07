from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('lead_intelligence', '0008_plantillamensaje')]

    operations = [
        migrations.CreateModel(name='RemarketingCampaign', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=160)),
            ('status', models.CharField(choices=[('draft', 'Borrador'), ('active', 'Activa'), ('paused', 'Pausada')], default='draft', max_length=12)),
            ('revision', models.PositiveIntegerField(default=1)),
            ('allowed_statuses', models.JSONField(default=list)),
            ('allowed_channels', models.JSONField(default=list)),
            ('agent_ids', models.JSONField(blank=True, default=list)),
            ('contact_sender', models.CharField(choices=[('agent', 'Humano'), ('any', 'Humano o bot')], default='agent', max_length=10)),
            ('daily_limit', models.PositiveIntegerField(default=100)),
            ('hourly_limit', models.PositiveIntegerField(default=20)),
            ('contact_limit', models.PositiveIntegerField(default=3)),
            ('min_gap_minutes', models.PositiveIntegerField(default=60)),
            ('window_margin_minutes', models.PositiveIntegerField(default=10)),
            ('start_hour', models.PositiveSmallIntegerField(default=9)),
            ('end_hour', models.PositiveSmallIntegerField(default=18)),
            ('weekdays', models.JSONField(default=list)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'ordering': ['-created_at']}),
        migrations.CreateModel(name='RemarketingRuntime', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('scan_after_id', models.BigIntegerField(default=0)),
        ]),
        migrations.CreateModel(name='RemarketingEnrollment', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('revision', models.PositiveIntegerField()),
            ('source_lead_id', models.BigIntegerField(db_index=True)),
            ('contact_key', models.CharField(db_index=True, max_length=128)),
            ('episode_key', models.CharField(max_length=64, unique=True)),
            ('anchor_at', models.DateTimeField()),
            ('last_inbound_at', models.DateTimeField()),
            ('policy', models.JSONField(default=dict)),
            ('context', models.JSONField(default=dict)),
            ('status', models.CharField(db_index=True, default='active', max_length=16)),
            ('stop_reason', models.CharField(blank=True, max_length=200)),
            ('response_at', models.DateTimeField(blank=True, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='enrollments', to='lead_intelligence.remarketingcampaign')),
        ]),
        migrations.CreateModel(name='RemarketingDelivery', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('position', models.PositiveIntegerField()),
            ('title', models.CharField(max_length=160)),
            ('body', models.TextField()),
            ('due_at', models.DateTimeField(db_index=True)),
            ('status', models.CharField(choices=[('pending', 'Programado'), ('sending', 'Enviando'), ('accepted', 'Aceptado por proveedor'), ('sent', 'Enviado'), ('delivered', 'Entregado'), ('failed', 'Fallido'), ('uncertain', 'Resultado incierto'), ('skipped', 'Omitido'), ('cancelled', 'Cancelado')], db_index=True, default='pending', max_length=16)),
            ('idempotency_key', models.UUIDField(unique=True)),
            ('attempted_at', models.DateTimeField(blank=True, null=True)),
            ('sent_at', models.DateTimeField(blank=True, null=True)),
            ('delivered_at', models.DateTimeField(blank=True, null=True)),
            ('response_at', models.DateTimeField(blank=True, null=True)),
            ('provider_message_id', models.CharField(blank=True, max_length=200)),
            ('reason', models.CharField(blank=True, max_length=240)),
            ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='deliveries', to='lead_intelligence.remarketingenrollment')),
        ], options={'ordering': ['due_at', 'pk']}),
        migrations.CreateModel(name='RemarketingStep', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('title', models.CharField(max_length=160)),
            ('body', models.TextField()),
            ('delay_minutes', models.PositiveIntegerField()),
            ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='lead_intelligence.remarketingcampaign')),
        ], options={'ordering': ['delay_minutes', 'pk']}),
        migrations.AddConstraint(model_name='remarketingdelivery', constraint=models.UniqueConstraint(fields=('enrollment', 'position'), name='rm_unique_delivery_step')),
        migrations.AddConstraint(model_name='remarketingstep', constraint=models.UniqueConstraint(fields=('campaign', 'delay_minutes'), name='rm_unique_step_delay')),
    ]
