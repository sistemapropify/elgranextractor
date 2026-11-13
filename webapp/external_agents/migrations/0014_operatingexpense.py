from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0013_payroll'),
    ]

    operations = [
        migrations.CreateModel(
            name='OperatingExpense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expense_category', models.CharField(choices=[('gastos_fijos', 'Gastos Fijos'), ('marketing', 'Gastos de Marketing')], db_index=True, max_length=30, verbose_name='Categoría')),
                ('subcategory', models.CharField(choices=[('alquiler', 'Alquiler'), ('mantenimiento', 'Mantenimiento'), ('seguros', 'Seguros'), ('administracion', 'Administración'), ('software', 'Software'), ('impuestos', 'Impuestos'), ('meta_ads', 'Meta Ads'), ('google_ads', 'Google Ads'), ('contenido', 'Contenido'), ('diseno', 'Diseño'), ('fotografia', 'Fotografía'), ('eventos', 'Eventos'), ('influencers', 'Influencers'), ('impresiones', 'Impresiones'), ('otros', 'Otros')], db_index=True, default='otros', max_length=30, verbose_name='Subcategoría')),
                ('concept', models.CharField(max_length=200, verbose_name='Concepto')),
                ('provider', models.CharField(blank=True, max_length=200, verbose_name='Proveedor')),
                ('reference', models.CharField(blank=True, max_length=200, verbose_name='Referencia')),
                ('recurrence', models.CharField(choices=[('unico', 'Único'), ('mensual', 'Mensual'), ('bimestral', 'Bimestral'), ('trimestral', 'Trimestral'), ('anual', 'Anual')], default='unico', max_length=20, verbose_name='Periodicidad')),
                ('currency_code', models.CharField(default='PEN', max_length=3, verbose_name='Moneda')),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto')),
                ('paid_amount', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Monto pagado')),
                ('expense_month', models.DateField(db_index=True, verbose_name='Mes correspondiente')),
                ('due_date', models.DateField(db_index=True, verbose_name='Vencimiento')),
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
                'verbose_name': 'Gasto operativo',
                'verbose_name_plural': 'Gastos operativos',
                'db_table': 'external_agents_operating_expense',
                'ordering': ['due_date', 'pk'],
            },
        ),
    ]
