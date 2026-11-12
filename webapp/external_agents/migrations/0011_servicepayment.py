from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0010_commissioncollection_deal_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServicePayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('concept', models.CharField(max_length=200, verbose_name='Concepto')),
                ('provider', models.CharField(blank=True, max_length=200, verbose_name='Proveedor')),
                ('reference', models.CharField(blank=True, max_length=200, verbose_name='Referencia')),
                ('category', models.CharField(choices=[('agua', 'Agua'), ('luz', 'Luz'), ('internet', 'Internet'), ('telefono', 'Teléfonos'), ('seguridad', 'Seguridad'), ('jardineria', 'Jardinería'), ('limpieza', 'Limpieza'), ('software', 'Software / IA'), ('mantenimiento', 'Mantenimiento'), ('otros', 'Otros')], db_index=True, default='otros', max_length=30, verbose_name='Categoría')),
                ('recurrence', models.CharField(choices=[('unico', 'Único'), ('mensual', 'Mensual'), ('bimestral', 'Bimestral'), ('trimestral', 'Trimestral'), ('anual', 'Anual')], default='unico', max_length=20, verbose_name='Periodicidad')),
                ('currency_code', models.CharField(default='PEN', max_length=3, verbose_name='Moneda')),
                ('estimated_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto estimado')),
                ('paid_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto pagado')),
                ('due_date', models.DateField(db_index=True, verbose_name='Fecha de vencimiento')),
                ('payment_date', models.DateField(blank=True, db_index=True, null=True, verbose_name='Fecha de pago')),
                ('reminder_days_before', models.PositiveSmallIntegerField(default=3, verbose_name='Días de anticipación')),
                ('status', models.CharField(choices=[('pendiente', 'Pendiente'), ('pagado', 'Pagado'), ('anulado', 'Anulado')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado')),
                ('payment_method', models.CharField(blank=True, max_length=50, verbose_name='Medio de pago')),
                ('account', models.CharField(blank=True, max_length=100, verbose_name='Cuenta de salida')),
                ('voucher', models.CharField(blank=True, max_length=100, verbose_name='Comprobante')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Observaciones')),
                ('created_by_username', models.CharField(blank=True, max_length=150, verbose_name='Registrado por')),
                ('updated_by_username', models.CharField(blank=True, max_length=150, verbose_name='Actualizado por')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado el')),
            ],
            options={
                'verbose_name': 'Pago de servicio',
                'verbose_name_plural': 'Pagos de servicios',
                'db_table': 'external_agents_service_payment',
                'ordering': ['due_date', 'pk'],
            },
        ),
    ]
