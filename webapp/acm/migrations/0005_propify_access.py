import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('acm', '0004_acmlink_component_history')]
    operations = [
        migrations.CreateModel(name='ACMRolePolicy', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('role_id', models.PositiveBigIntegerField(unique=True)),
            ('permissions', models.JSONField(default=dict)),
            ('revision', models.PositiveIntegerField(default=1)),
            ('updated_by', models.CharField(max_length=100)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='ACMRoleAudit', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('role_id', models.PositiveBigIntegerField(db_index=True)),
            ('actor_id', models.CharField(max_length=100)),
            ('before', models.JSONField(default=dict)),
            ('after', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.CreateModel(name='ACMPortalAnalysis', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('owner_id', models.CharField(db_index=True, max_length=100)),
            ('fingerprint', models.CharField(max_length=64)),
            ('snapshot', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'ordering': ['-created_at']}),
        migrations.AddConstraint(model_name='acmportalanalysis', constraint=models.UniqueConstraint(fields=('owner_id', 'fingerprint'), name='acm_owner_fingerprint_unique')),
        migrations.CreateModel(name='ACMPhotoReview', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('digest', models.CharField(max_length=64, unique=True)),
            ('approved', models.BooleanField(default=False)),
            ('reviewed_by', models.CharField(max_length=100)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
    ]
