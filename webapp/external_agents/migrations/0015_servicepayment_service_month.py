from django.db import migrations, models


def fill_service_month(apps, schema_editor):
    ServicePayment = apps.get_model('external_agents', 'ServicePayment')
    for payment in ServicePayment.objects.filter(service_month__isnull=True):
        payment.service_month = payment.due_date.replace(day=1)
        payment.save(update_fields=['service_month'])


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0014_operatingexpense'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicepayment',
            name='service_month',
            field=models.DateField(
                db_index=True,
                null=True,
                verbose_name='Mes correspondiente',
            ),
        ),
        migrations.RunPython(fill_service_month, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='servicepayment',
            name='service_month',
            field=models.DateField(
                db_index=True,
                verbose_name='Mes correspondiente',
            ),
        ),
    ]
