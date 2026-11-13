from datetime import date
from decimal import Decimal

from django.db import migrations


SEAL_PAYMENTS = [
    (date(2026, 10, 1), date(2026, 10, 28), date(2026, 11, 5), Decimal('312.50'), True),
    (date(2026, 9, 1), date(2026, 9, 27), date(2026, 10, 6), Decimal('259.50'), True),
    (date(2026, 8, 1), date(2026, 8, 27), date(2026, 9, 4), Decimal('220.20'), True),
    (date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 4), Decimal('237.00'), True),
    (date(2026, 6, 1), date(2026, 7, 6), date(2026, 7, 4), Decimal('487.30'), True),
    (date(2026, 5, 1), None, date(2026, 6, 5), Decimal('245.80'), False),
]


def import_seal_payments(apps, schema_editor):
    ServicePayment = apps.get_model('external_agents', 'ServicePayment')
    for service_month, payment_date, due_date, amount, is_paid in SEAL_PAYMENTS:
        exists = ServicePayment.objects.filter(
            provider__iexact='SEAL',
            service_month=service_month,
            reference__icontains='95924',
        ).exists()
        if exists:
            continue
        ServicePayment.objects.create(
            concept='Recibo de luz SEAL',
            provider='SEAL',
            reference='Suministro 95924 · Sucursal 1',
            financial_category='servicios',
            subcategory='luz',
            recurrence='mensual',
            currency_code='PEN',
            estimated_amount=amount,
            paid_amount=amount if is_paid else Decimal('0.00'),
            service_month=service_month,
            due_date=due_date,
            payment_date=payment_date,
            reminder_days_before=3,
            status='pagado' if is_paid else 'pendiente',
            notes=(
                'Importado del historial de SEAL. '
                'Duplicado: https://oficinavirtual.seal.com.pe/'
                'Suministros/Detalle?strCodigoSuministro=95924'
                '&strCodigoSucursal=1'
            ),
            created_by_username='importacion-seal',
            updated_by_username='importacion-seal',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0015_servicepayment_service_month'),
    ]

    operations = [
        migrations.RunPython(import_seal_payments, migrations.RunPython.noop),
    ]
