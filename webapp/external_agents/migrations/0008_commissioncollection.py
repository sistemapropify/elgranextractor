from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0007_commissionpayment'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommissionCollection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_code', models.CharField(db_index=True, max_length=100, unique=True, verbose_name='Código de operación')),
                ('property_name', models.CharField(blank=True, max_length=300, verbose_name='Propiedad')),
                ('amount_to_collect', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto a cobrar al propietario')),
                ('collected_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto cobrado')),
                ('closing_date', models.DateField(blank=True, null=True, verbose_name='Fecha de cierre')),
                ('status', models.CharField(choices=[('pendiente', 'Pendiente'), ('parcial', 'Parcial'), ('cobrado', 'Cobrado')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado')),
                ('created_by_username', models.CharField(blank=True, max_length=150, verbose_name='Registrado por')),
                ('updated_by_username', models.CharField(blank=True, max_length=150, verbose_name='Actualizado por')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado el')),
            ],
            options={
                'verbose_name': 'Cobro de comisión',
                'verbose_name_plural': 'Cobros de comisiones',
                'db_table': 'external_agents_commission_collection',
                'ordering': ['-closing_date', '-pk'],
            },
        ),
    ]
