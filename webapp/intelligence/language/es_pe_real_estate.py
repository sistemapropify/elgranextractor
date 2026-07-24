"""Léxico inmobiliario peruano controlado y versionado.

Los alias de este módulo son datos deterministas: una expresión nueva solo
debe activarse después de ser revisada y cubierta por pruebas.
"""

PROPERTY_TYPE_ALIASES = {
    "depa": "Departamento",
    "depas": "Departamento",
    "depto": "Departamento",
    "deptos": "Departamento",
    "dpto": "Departamento",
    "dptos": "Departamento",
    "flat": "Departamento",
    "jato": "Casa",
    "casita": "Casa",
    "lote": "Terreno",
    "lotecito": "Terreno",
    "terreo": "Terreno",
    "terreos": "Terreno",
    "tiendita": "Local",
    "localcito": "Local",
}

DISTRICT_ALIASES = {
    "jlbyr": "Jose Luis Bustamante",
    "jlb y r": "Jose Luis Bustamante",
    "cayma baja": "Cayma",
    "cayma alta": "Cayma",
}

SPANISH_SMALL_NUMBERS = {
    "un": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "veinte": 20,
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "cien": 100,
}
