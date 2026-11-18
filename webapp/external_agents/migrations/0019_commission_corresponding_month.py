from django.db import migrations, models


def _month_start(value):
    return value.replace(day=1) if value else None


def fill_commission_months(apps, schema_editor):
    CommissionCollection = apps.get_model(
        'external_agents',
        'CommissionCollection',
    )
    CommissionCollectionEntry = apps.get_model(
        'external_agents',
        'CommissionCollectionEntry',
    )
    CommissionPayment = apps.get_model(
        'external_agents',
        'CommissionPayment',
    )

    collection_months = {}
    for collection in CommissionCollection.objects.all().iterator():
        basis = (
            collection.closing_date
            or collection.created_at.date()
        )
        collection.corresponding_month = _month_start(basis)
        collection.save(update_fields=['corresponding_month'])
        collection_months[collection.pk] = collection.corresponding_month

    for entry in CommissionCollectionEntry.objects.all().iterator():
        entry.corresponding_month = (
            collection_months.get(entry.collection_id)
            or _month_start(entry.collection_date)
            or _month_start(entry.created_at.date())
        )
        entry.save(update_fields=['corresponding_month'])

    collection_months_by_code = dict(
        CommissionCollection.objects.values_list(
            'operation_code',
            'corresponding_month',
        )
    )
    for payment in CommissionPayment.objects.all().iterator():
        payment.corresponding_month = (
            collection_months_by_code.get(payment.operation_code)
            or _month_start(payment.due_date)
            or _month_start(payment.payment_date)
            or _month_start(payment.created_at.date())
        )
        payment.save(update_fields=['corresponding_month'])


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0018_financesubmissiontoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='commissionpayment',
            name='corresponding_month',
            field=models.DateField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name='Mes correspondiente',
            ),
        ),
        migrations.AddField(
            model_name='commissioncollection',
            name='corresponding_month',
            field=models.DateField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name='Mes correspondiente',
            ),
        ),
        migrations.AddField(
            model_name='commissioncollectionentry',
            name='corresponding_month',
            field=models.DateField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name='Mes correspondiente',
            ),
        ),
        migrations.RunPython(
            fill_commission_months,
            migrations.RunPython.noop,
        ),
    ]
