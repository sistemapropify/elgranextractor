"""PlantillaMensaje para autorizar/analizar múltiples plantillas de remarketing.

El dashboard de remarketing analizaba una única plantilla fija en código
(``REMARKETING_*`` en lead_intelligence/remarketing.py). Esta migración crea
la tabla ``prometeo_plantilla_mensaje`` y la siembra con:

1. La plantilla validada original ("Hola de nuevo… puedo coordinarte una visita").
2. Una segunda plantilla de seguimiento: "¿Pudiste leer mi mensaje? Coméntame
   que más te gustaría saber de la propiedad para darte más detalles."
"""

from django.db import migrations, models


def seed_plantillas(apps, schema_editor):
    PlantillaMensaje = apps.get_model("lead_intelligence", "PlantillaMensaje")
    defaults = [
        {
            "codigo": "hola_de_nuevo_propiedad",
            "titulo": "Intento 1 · Hola de nuevo",
            "cuerpo": (
                "Hola de nuevo 👋 Si te sigue interesando la propiedad, puedo "
                "coordinarte una visita. O si prefieres, dime qué estás buscando "
                "y te muestro otras opciones."
            ),
            "orden": 1,
            "frase_condicion": (
                "hola de nuevo si te sigue interesando la propiedad puedo coordinarte una visita"
            ),
            "regex_condicion": "",
            "sql_hint": "%Hola de nuevo%",
            "activa": True,
        },
        {
            "codigo": "pudiste_leer_mi_mensaje",
            "titulo": "Intento 2 · ¿Pudiste leer mi mensaje?",
            "cuerpo": (
                "¿Pudiste leer mi mensaje? Coméntame que más te gustaría saber "
                "de la propiedad para darte más detalles."
            ),
            "orden": 2,
            "frase_condicion": "pudiste leer mi mensaje",
            "regex_condicion": "",
            "sql_hint": "%Pudiste leer mi mensaje%",
            "activa": True,
        },
    ]
    for plantilla in defaults:
        PlantillaMensaje.objects.get_or_create(
            codigo=plantilla["codigo"],
            defaults=plantilla,
        )


def unseed_plantillas(apps, schema_editor):
    PlantillaMensaje = apps.get_model("lead_intelligence", "PlantillaMensaje")
    PlantillaMensaje.objects.filter(
        codigo__in=["hola_de_nuevo_propiedad", "pudiste_leer_mi_mensaje"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lead_intelligence", "0007_analysisrun_period"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlantillaMensaje",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("codigo", models.CharField(max_length=100, unique=True)),
                ("titulo", models.CharField(max_length=200, verbose_name="Título de la plantilla")),
                (
                    "cuerpo",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Texto literal de la plantilla (solo informativo/visual).",
                    ),
                ),
                (
                    "orden",
                    models.PositiveSmallIntegerField(
                        default=1,
                        help_text="Ej.: 1, 2, 3…",
                        verbose_name="Orden / intento",
                    ),
                ),
                (
                    "frase_condicion",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Frase que el mensaje debe contener para contarse. Se normaliza "
                            "(sin mayúsculas/signos). Ej.: pudiste leer mi mensaje"
                        ),
                        max_length=500,
                        verbose_name="Condición (frase)",
                    ),
                ),
                (
                    "regex_condicion",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Patrón regex opcional, más preciso que la frase.",
                        max_length=500,
                        verbose_name="Condición (regex, opcional)",
                    ),
                ),
                (
                    "sql_hint",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Patrón LIKE amplio para prefiltrar el CRM. Ej.: %Pudiste leer mi mensaje%",
                        max_length=500,
                        verbose_name="Patrón SQL LIKE",
                    ),
                ),
                (
                    "activa",
                    models.BooleanField(
                        default=True,
                        help_text="Solo las plantillas activas se autorizan en el análisis.",
                    ),
                ),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prometeo_plantilla_mensaje",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.RunPython(seed_plantillas, unseed_plantillas),
    ]
