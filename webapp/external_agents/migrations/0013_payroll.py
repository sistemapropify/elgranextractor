from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0012_servicepayment_financial_hierarchy'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayrollEmployee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200, verbose_name='Trabajador')),
                ('document_number', models.CharField(blank=True, db_index=True, max_length=20, verbose_name='DNI')),
                ('position', models.CharField(blank=True, max_length=150, verbose_name='Cargo')),
                ('area', models.CharField(blank=True, max_length=150, verbose_name='Área')),
                ('base_salary', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Sueldo base')),
                ('currency_code', models.CharField(default='PEN', max_length=3, verbose_name='Moneda')),
                ('pension_system', models.CharField(choices=[('afp', 'AFP'), ('onp', 'ONP'), ('ninguno', 'Sin pensión')], default='afp', max_length=20, verbose_name='Sistema de pensión')),
                ('pension_pct', models.DecimalField(decimal_places=2, default=Decimal('10.00'), max_digits=5, verbose_name='% descuento pensionario')),
                ('bank_account', models.CharField(blank=True, max_length=100, verbose_name='Cuenta bancaria')),
                ('hire_date', models.DateField(blank=True, null=True, verbose_name='Fecha de ingreso')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado el')),
            ],
            options={
                'verbose_name': 'Trabajador de planilla',
                'verbose_name_plural': 'Trabajadores de planilla',
                'db_table': 'external_agents_payroll_employee',
                'ordering': ['full_name', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='PayrollEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.DateField(db_index=True, verbose_name='Periodo')),
                ('financial_category', models.CharField(db_index=True, default='planillas', max_length=30, verbose_name='Categoría financiera')),
                ('movement_type', models.CharField(choices=[('ingreso', 'Ingreso'), ('egreso', 'Egreso')], db_index=True, default='egreso', max_length=20, verbose_name='Tipo de movimiento')),
                ('base_salary', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Sueldo base')),
                ('family_allowance', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Asignación familiar')),
                ('bonuses', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Bonificaciones')),
                ('overtime', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Horas extras')),
                ('other_income', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Otros ingresos')),
                ('commissions', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Comisiones')),
                ('pension_deduction', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Descuento AFP / ONP')),
                ('income_tax', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Retención renta')),
                ('other_deductions', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Otros descuentos')),
                ('essalud_rate', models.DecimalField(decimal_places=2, default=Decimal('9.00'), max_digits=5, verbose_name='% EsSalud empleador')),
                ('currency_code', models.CharField(default='PEN', max_length=3, verbose_name='Moneda')),
                ('status', models.CharField(choices=[('pendiente', 'Pendiente'), ('pagado', 'Pagado')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado')),
                ('payment_date', models.DateField(blank=True, db_index=True, null=True, verbose_name='Fecha de pago')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Observaciones')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado el')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_entries', to='external_agents.payrollemployee', verbose_name='Trabajador')),
            ],
            options={
                'verbose_name': 'Fila de planilla',
                'verbose_name_plural': 'Planillas',
                'db_table': 'external_agents_payroll_entry',
                'ordering': ['employee__full_name', 'pk'],
            },
        ),
        migrations.AddConstraint(
            model_name='payrollentry',
            constraint=models.UniqueConstraint(
                fields=('employee', 'period'),
                name='unique_payroll_employee_period',
            ),
        ),
    ]
