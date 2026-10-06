"""
Carga la leyenda de usos de suelo del plano de zonificación del PDM.

Los códigos y colores se leyeron directamente de la leyenda impresa del PDF
(recuadros vectoriales y su rótulo), así que coinciden con los del mapa.
"""

from django.db import migrations

# (código, descripción, categoría, color HEX)
LEYENDA = [
    ('RDB', 'Residencial densidad baja', 'Residencial', '#d2d196'),
    ('RDM-1', 'Residencial densidad media tipo 1', 'Residencial', '#fbfe93'),
    ('RDM-2', 'Residencial densidad media tipo 2', 'Residencial', '#fde41d'),
    ('RDA-1', 'Residencial densidad alta tipo 1', 'Residencial', '#ffb70b'),
    ('RDA-2', 'Residencial densidad alta tipo 2', 'Residencial', '#d6882d'),
    ('I1R', 'Vivienda taller', 'Residencial', '#feffd2'),
    ('CE', 'Comercio especializado', 'Comercio', '#b03130'),
    ('CS', 'Comercio sectorial', 'Comercio', '#ff9d9d'),
    ('CZ', 'Comercio zonal', 'Comercio', '#ff0000'),
    ('CIn', 'Comercio industrial', 'Comercio', '#800200'),
    ('CM', 'Comercio metropolitano', 'Comercio', '#ff615f'),
    ('I-1', 'Industria elemental', 'Industria', '#bc81ce'),
    ('I-2', 'Industria liviana', 'Industria', '#932ab2'),
    ('ZR', 'Zona de recreación', 'Equipamiento', '#1db303'),
    ('EDU', 'Educación', 'Equipamiento', '#3883c0'),
    ('SAL', 'Salud', 'Equipamiento', '#56c4d4'),
    ('OU1', 'Usos especiales tipo 1', 'Equipamiento', '#989898'),
    ('OU2', 'Usos especiales tipo 2', 'Equipamiento', '#4b4b4b'),
    ('ZRE-CH', 'Zona de reglamentación especial - Centro histórico',
     'Reglamentación especial', '#e0b3b3'),
    ('ZRE-PA', 'Zona de reglamentación especial - Patrimonio agrícola',
     'Reglamentación especial', '#739973'),
    ('ZRE-PN', 'Zona de reglamentación especial - Patrimonio natural',
     'Reglamentación especial', '#7d4f5a'),
    ('ZRE-PP', 'Zona de reglamentación especial - Patrimonio paisajista',
     'Reglamentación especial', '#bb7f85'),
    ('ZRE-RI1', 'Zona de reglamentación especial - Riesgos tipo 1',
     'Reglamentación especial', '#aca661'),
    ('ZRE-RI2', 'Zona de reglamentación especial - Riesgos tipo 2',
     'Reglamentación especial', '#a6ae48'),
    ('ZRE-RU', 'Zona de reglamentación especial - Renovación urbana',
     'Reglamentación especial', '#663849'),
    ('ZAQ', 'Zona arqueológica', 'Otros', '#cecece'),
    ('ZM', 'Zona monumental', 'Otros', '#502936'),
    ('ZRP', 'Zona de reserva paisajista', 'Otros', '#47b368'),
    ('EA', 'Expansión agrícola', 'Otros', '#84dca6'),
    ('ZA', 'Zona agrícola', 'Otros', '#84dca6'),
]


def cargar_leyenda(apps, schema_editor):
    ZonaUso = apps.get_model('cuadrantizacion', 'ZonaUso')
    for orden, (codigo, nombre, categoria, color) in enumerate(LEYENDA):
        ZonaUso.objects.update_or_create(
            codigo=codigo,
            defaults={
                'nombre': nombre,
                'categoria': categoria,
                'color': color,
                'orden': orden,
                'activo': True,
            },
        )


def borrar_leyenda(apps, schema_editor):
    ZonaUso = apps.get_model('cuadrantizacion', 'ZonaUso')
    ZonaUso.objects.filter(codigo__in=[fila[0] for fila in LEYENDA]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cuadrantizacion', '0007_zonauso'),
    ]

    operations = [
        migrations.RunPython(cargar_leyenda, borrar_leyenda),
    ]
