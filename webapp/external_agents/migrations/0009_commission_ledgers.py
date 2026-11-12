import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0008_commissioncollection'),
    ]

    operations = [
        migrations.AddField(
            model_name='commissionpayment',
            name='currency_code',
            field=models.CharField(
                default='USD',
                max_length=3,
                verbose_name='Moneda',
            ),
        ),
        migrations.AddField(
            model_name='commissioncollection',
            name='amount_for_agents',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=14,
                verbose_name='Comisión para agentes',
            ),
        ),
        migrations.AddField(
            model_name='commissioncollection',
            name='amount_for_brokers',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=14,
                verbose_name='Comisión para brokers',
            ),
        ),
        migrations.AddField(
            model_name='commissioncollection',
            name='amount_for_propify',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=14,
                verbose_name='Comisión para Propify',
            ),
        ),
        migrations.AddField(
            model_name='commissioncollection',
            name='currency_code',
            field=models.CharField(
                default='USD',
                max_length=3,
                verbose_name='Moneda',
            ),
        ),
        migrations.CreateModel(
            name='CommissionCollectionEntry',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'amount',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=14,
                        verbose_name='Importe recibido',
                    ),
                ),
                (
                    'collection_date',
                    models.DateField(
                        db_index=True,
                        verbose_name='Fecha del abono',
                    ),
                ),
                (
                    'payment_method',
                    models.CharField(
                        blank=True,
                        max_length=50,
                        verbose_name='Medio de pago',
                    ),
                ),
                (
                    'account',
                    models.CharField(
                        blank=True,
                        max_length=100,
                        verbose_name='Cuenta de destino',
                    ),
                ),
                (
                    'voucher',
                    models.CharField(
                        blank=True,
                        max_length=100,
                        verbose_name='Comprobante',
                    ),
                ),
                (
                    'notes',
                    models.TextField(
                        blank=True,
                        default='',
                        verbose_name='Observaciones',
                    ),
                ),
                (
                    'registered_by_username',
                    models.CharField(
                        blank=True,
                        max_length=150,
                        verbose_name='Registrado por',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Creado el',
                    ),
                ),
                (
                    'collection',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='entries',
                        to='external_agents.commissioncollection',
                        verbose_name='Cobro de comisión',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Abono de comisión',
                'verbose_name_plural': 'Abonos de comisiones',
                'db_table': 'external_agents_commission_collection_entry',
                'ordering': ['-collection_date', '-pk'],
            },
        ),
    ]
