import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospects', '0014_propertyprospect_crm_cronologia'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_username', models.CharField(db_index=True, max_length=150, verbose_name='Usuario')),
                ('event_type', models.CharField(choices=[('acceso', 'Acceso al módulo'), ('navegacion', 'Navegación'), ('filtro', 'Filtro aplicado'), ('busqueda', 'Búsqueda'), ('prospecto_visto', 'Prospecto abierto'), ('prospecto_editado', 'Prospecto editado'), ('estado_cambiado', 'Cambio de estado'), ('captura_creada', 'Captura creada'), ('asignacion', 'Tomar / soltar prospección'), ('comentario', 'Comentario'), ('exportacion', 'Exportación'), ('otro', 'Otra acción')], db_index=True, max_length=32, verbose_name='Tipo de evento')),
                ('description', models.CharField(max_length=500, verbose_name='Descripción')),
                ('user_agent', models.CharField(blank=True, default='', max_length=400, verbose_name='User agent')),
                ('path', models.CharField(blank=True, default='', max_length=300, verbose_name='Ruta')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha y hora')),
                ('prospect', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to='prospects.propertyprospect', verbose_name='Prospección')),
            ],
            options={
                'verbose_name': 'Actividad',
                'verbose_name_plural': 'Actividades',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['-created_at', 'event_type'], name='prospect_act_fecha_tipo'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['user_username', '-created_at'], name='prospect_act_user_fecha'),
        ),
    ]
