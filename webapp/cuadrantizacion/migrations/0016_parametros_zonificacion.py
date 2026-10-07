"""
Carga los parámetros normativos de cada zona desde la memoria del PDM.

Estos cuadros salen del Capítulo IV del Plan (fichas de zonificación) y son los
que se muestran en el ACM al detectar la zona de un marcador: densidad neta,
lote y frente mínimo, altura de edificación, coeficiente, área libre, retiros,
alineamiento de fachada y estacionamiento.
"""

from django.db import migrations

PARAMETROS = {
    "RDB": {
        "bloques": [{
            "tipologia": "Unifamiliar", "densidad": "Hasta 165 hab/ha",
            "lote_minimo": "300.00 m2", "frente_minimo": "12.00 ml",
            "altura": "2 pisos", "coeficiente": "1.20", "area_libre": "40 %",
            "retiros": "Según normatividad de retiros",
            "alineamiento": "Según normas de la Municipalidad Distrital",
            "estacionamiento": "1 c/vivienda",
        }],
        "usos_compatibles": "CV, ZR",
        "notas": [],
    },
    "RDM-1": {
        "bloques": [
            {
                "tipologia": "Unifamiliar", "densidad": "De 166 a 900 hab/ha",
                "lote_minimo": "90.00 m2", "frente_minimo": "8.00 ml",
                "altura": "3 pisos", "coeficiente": "2.10", "area_libre": "30 %",
                "retiros": "Según normatividad de retiros",
                "alineamiento": "Según normas de la Municipalidad Distrital",
                "estacionamiento": "1 c/2 viviendas",
            },
            {
                "tipologia": "Multifamiliar", "densidad": "166 a 1300 hab/ha",
                "lote_minimo": "150.00 m2", "frente_minimo": "8.00 ml",
                "altura": "4 pisos", "coeficiente": "2.80", "area_libre": "35 %",
                "retiros": "Según normatividad de retiros",
                "alineamiento": "Según normas de la Municipalidad Distrital",
                "estacionamiento": "1 c/2 viviendas",
            },
        ],
        "usos_compatibles": "CV, CS, E-1, H-1, ZR",
        "notas": [],
    },
    "RDM-2": {
        "bloques": [
            {
                "tipologia": "Multifamiliar", "densidad": "De 901 a 1400 hab/ha",
                "lote_minimo": "150.00 m2", "frente_minimo": "8.00 ml",
                "altura": "5 pisos", "coeficiente": "3.50", "area_libre": "35 %",
                "retiros": "Según normatividad de retiros",
                "alineamiento": "Según normas de la Municipalidad Distrital",
                "estacionamiento": "1 c/2 viviendas",
            },
            {
                "tipologia": "Multifamiliar (*)", "densidad": "901 a 1400 hab/ha",
                "lote_minimo": "180.00 m2", "frente_minimo": "8.00 ml",
                "altura": "6 pisos", "coeficiente": "4.20", "area_libre": "40 %",
                "retiros": "Según normatividad de retiros",
                "alineamiento": "Según normas de la Municipalidad Distrital",
                "estacionamiento": "1 c/2 viviendas",
            },
        ],
        "usos_compatibles": "CV, CS, CZ, E-1, H1, H2, ZR",
        "notas": ["(*) Con frente a vías mayores a 18 ml de sección y/o frente a parques"],
    },
    "RDA-1": {
        "bloques": [
            {
                "tipologia": "Multifamiliar", "densidad": "De 1401 a 2250 hab/ha",
                "lote_minimo": "240.00 m2", "frente_minimo": "15.00 ml",
                "altura": "6 pisos", "coeficiente": "1.5 (a+r) ** · 4.20",
                "area_libre": "45 %", "retiros": "Según normatividad de retiros",
                "alineamiento": "Según normas de la Municipalidad Distrital",
                "estacionamiento": "1 c/2 viviendas",
            },
            {
                "tipologia": "Multifamiliar (*)", "densidad": "1401 a 2250 hab/ha",
                "lote_minimo": "300.00 m2", "frente_minimo": "15.00 ml",
                "altura": "7 pisos", "coeficiente": "1.5 (a+r) ** · 4.20",
                "area_libre": "50 %", "retiros": "Según normatividad de retiros",
                "alineamiento": "Según normas de la Municipalidad Distrital",
                "estacionamiento": "1 c/2 viviendas",
            },
        ],
        "usos_compatibles": "CV, CS, CZ, E-1, H1, H2, ZR",
        "notas": [
            "(*) Con frente a vías mayores a 18 ml de sección y/o frente a parques",
            "(**) a = ancho de la vía / r = retiro de la edificación.",
            "Área libre: 45 % + 5 % por cada piso adicional respecto de la altura de edificación.",
        ],
    },
    "RDA-2": {
        "bloques": [{
            "tipologia": "Multifamiliar (*)", "densidad": "De 2251 a 2800 hab/ha",
            "lote_minimo": "600.00 m2", "frente_minimo": "15.00 ml",
            "altura": "10 pisos", "coeficiente": "1.5 (a+r) ** · 6.00",
            "area_libre": "55 %", "retiros": "Según normatividad de retiros",
            "alineamiento": "Según normas de la Municipalidad Distrital",
            "estacionamiento": "1 c/2 viviendas",
        }],
        "usos_compatibles": "CZ, CM, E-1, H1, H2, ZR",
        "notas": [
            "(*) Con frente a vías mayores a 18 ml de sección y/o frente a parques",
            "(**) a = ancho de la vía / r = retiro de la edificación.",
            "Área libre: 55 % + 5 % por cada piso adicional respecto de la altura de edificación.",
        ],
    },
    "I1R": {
        "bloques": [{
            "tipologia": "Unifamiliar", "densidad": "Hasta 900 hab/ha",
            "lote_minimo": "150.00 m2", "frente_minimo": "8.00 ml",
            "altura": "4 pisos", "coeficiente": "2.80", "area_libre": "30 %",
            "retiros": "Según normatividad de retiros",
            "alineamiento": "Según normas de la Municipalidad Distrital",
            "estacionamiento": "1 c/3 viviendas",
        }],
        "usos_compatibles": "RDB, I1R, CV, CS, I-1",
        "notas": [
            "( * ) Con frente a vías mayores de 18 ml de sección y/o frente a parques",
            "( **) Se destinará como mínimo el 50 % del área libre a espacios ocupados por "
            "construcción liviana o retiros.",
        ],
    },
}


def cargar(apps, schema_editor):
    ZonaUso = apps.get_model('cuadrantizacion', 'ZonaUso')
    for codigo, parametros in PARAMETROS.items():
        ZonaUso.objects.filter(codigo=codigo).update(parametros=parametros)


def descargar(apps, schema_editor):
    ZonaUso = apps.get_model('cuadrantizacion', 'ZonaUso')
    ZonaUso.objects.filter(codigo__in=list(PARAMETROS)).update(parametros={})


class Migration(migrations.Migration):

    dependencies = [
        ('cuadrantizacion', '0015_zonauso_parametros'),
    ]

    operations = [
        migrations.RunPython(cargar, descargar),
    ]
