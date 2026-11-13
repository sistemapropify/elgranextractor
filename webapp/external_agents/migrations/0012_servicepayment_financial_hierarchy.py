from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_agents', '0011_servicepayment'),
    ]

    operations = [
        migrations.RenameField(
            model_name='servicepayment',
            old_name='category',
            new_name='subcategory',
        ),
        migrations.AlterField(
            model_name='servicepayment',
            name='subcategory',
            field=models.CharField(
                choices=[
                    ('agua', 'Agua'),
                    ('luz', 'Luz'),
                    ('internet', 'Internet'),
                    ('telefono', 'Teléfonos'),
                    ('seguridad', 'Seguridad'),
                    ('jardineria', 'Jardinería'),
                    ('limpieza', 'Limpieza'),
                    ('software', 'Software / IA'),
                    ('mantenimiento', 'Mantenimiento'),
                    ('otros', 'Otros'),
                ],
                db_index=True,
                default='otros',
                max_length=30,
                verbose_name='Subcategoría',
            ),
        ),
        migrations.AddField(
            model_name='servicepayment',
            name='financial_category',
            field=models.CharField(
                choices=[
                    ('servicios', 'Servicios'),
                    ('comisiones', 'Pago de comisiones'),
                ],
                db_index=True,
                default='servicios',
                max_length=30,
                verbose_name='Categoría financiera',
            ),
        ),
    ]
