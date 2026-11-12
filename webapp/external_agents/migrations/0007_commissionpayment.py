from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0006_externalagent_observations'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommissionPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_code', models.CharField(blank=True, db_index=True, max_length=100, verbose_name='Código de operación')),
                ('property_name', models.CharField(blank=True, max_length=300, verbose_name='Propiedad')),
                ('beneficiary_type', models.CharField(choices=[('propify', 'Propify'), ('agente_vendedor', 'Agente vendedor'), ('agente_comprador', 'Agente comprador'), ('otro', 'Otro')], db_index=True, max_length=30, verbose_name='Tipo de beneficiario')),
                ('beneficiary_name', models.CharField(blank=True, max_length=300, verbose_name='Beneficiario')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Importe a pagar')),
                ('due_date', models.DateField(blank=True, db_index=True, null=True, verbose_name='Fecha de vencimiento')),
                ('payment_date', models.DateField(blank=True, null=True, verbose_name='Fecha de pago')),
                ('status', models.CharField(choices=[('pendiente', 'Pendiente'), ('pagado', 'Pagado'), ('anulado', 'Anulado')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado')),
                ('payment_method', models.CharField(blank=True, max_length=50, verbose_name='Medio de pago')),
                ('account', models.CharField(blank=True, max_length=100, verbose_name='Cuenta de salida')),
                ('voucher', models.CharField(blank=True, max_length=100, verbose_name='Comprobante')),
                ('approved_by', models.CharField(blank=True, max_length=150, verbose_name='Aprobado por')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Observaciones')),
                ('created_by_username', models.CharField(blank=True, max_length=150, verbose_name='Registrado por')),
                ('updated_by_username', models.CharField(blank=True, max_length=150, verbose_name='Actualizado por')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado el')),
            ],
            options={
                'verbose_name': 'Pago de comisión',
                'verbose_name_plural': 'Pagos de comisiones',
                'db_table': 'external_agents_commission_payment',
                'ordering': ['-due_date', '-pk'],
            },
        ),
    ]
