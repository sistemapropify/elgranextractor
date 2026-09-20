from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('cuadrantizacion', '0003_alter_zonavalor_coordenadas')]

    operations = [
        migrations.AlterField(
            model_name='zonavalor', name='nivel',
            field=models.CharField(
                max_length=20, default='zona',
                help_text='Nivel jerárquico de la zona',
                choices=[('pais', 'País'), ('departamento', 'Departamento'),
                         ('provincia', 'Provincia'), ('distrito', 'Distrito'),
                         ('zona', 'Zona'), ('subzona', 'Subzona'),
                         ('cuadrante', 'Cuadrante')],
            ),
        ),
    ]
