from datetime import date

from django.db import migrations


SEAL_MONTHS = [
    date(2026, 5, 1),
    date(2026, 6, 1),
    date(2026, 7, 1),
    date(2026, 8, 1),
    date(2026, 9, 1),
    date(2026, 10, 1),
]


def clean_seal_records(apps, schema_editor):
    ServicePayment = apps.get_model('external_agents', 'ServicePayment')
    for month in SEAL_MONTHS:
        records = list(
            ServicePayment.objects.filter(
                provider__iexact='SEAL',
                reference__icontains='95924',
                service_month=month,
            ).order_by('id')
        )
        if not records:
            continue
        keeper = records[0]
        keeper.status = 'pagado'
        keeper.paid_amount = keeper.estimated_amount
        keeper.save(update_fields=['status', 'paid_amount'])
        for duplicate in records[1:]:
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0016_import_seal_service_payments'),
    ]

    operations = [
        migrations.RunPython(clean_seal_records, migrations.RunPython.noop),
    ]
