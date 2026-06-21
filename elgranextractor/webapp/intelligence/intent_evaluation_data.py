"""Dataset de evaluación para el clasificador de intenciones."""

from .services.intent_classifier import IntentType

INTENT_EVALUATION_SAMPLES = [
    {
        'question': '¿Cuál es el precio promedio por metro cuadrado en Cayma?',
        'expected_intent': IntentType.PRICE_QUERY,
        'expected_skill': 'reporte_precios_zona',
        'expected_description': 'Consulta de precio por m2 en una zona concreta',
    },
    {
        'question': 'Promedio de metro cuadrado en Yanahuara para departamentos',
        'expected_intent': IntentType.PRICE_QUERY,
        'expected_skill': 'reporte_precios_zona',
        'expected_description': 'Consulta de precio promedio m2 para tipo y zona',
    },
    {
        'question': '¿Qué precio tiene un departamento en Miraflores?',
        'expected_intent': IntentType.PRICE_QUERY,
        'expected_skill': 'reporte_precios_zona',
        'expected_description': 'Consulta de precio por zona y tipo',
    },
    {
        'question': '¿Cuál es el valor de un terreno en Socabaya?',
        'expected_intent': IntentType.PRICE_QUERY,
        'expected_skill': 'reporte_precios_zona',
        'expected_description': 'Consulta de precio para terrenos en zona',
    },
    {
        'question': 'Multiplica 3 por 5',
        'expected_intent': IntentType.GENERAL,
        'expected_skill': 'multiplicacion',
        'expected_description': 'Operación matemática básica que debe enrutar a skill de multiplicación',
    },
    {
        'question': 'Quiero una casa en Cayma con 3 habitaciones',
        'expected_intent': IntentType.PROPERTY_SEARCH,
        'expected_skill': None,
        'expected_description': 'Búsqueda de propiedades sin skill específica de precios',
    },
    {
        'question': '¿Qué tendencias muestra el mercado inmobiliario?',
        'expected_intent': IntentType.MARKET_QUERY,
        'expected_skill': None,
        'expected_description': 'Consulta de mercado general',
    },
    {
        'question': '¿Qué ley se aplica para la compra de un terreno?',
        'expected_intent': IntentType.LEGAL_QUERY,
        'expected_skill': None,
        'expected_description': 'Consulta legal relacionada con normativa inmobiliaria',
    },
    {
        'question': 'Cómo me llamo',
        'expected_intent': IntentType.USER_INFO,
        'expected_skill': None,
        'expected_description': 'Pregunta de información personal del usuario',
    },
    {
        'question': 'Hola, buenos días',
        'expected_intent': IntentType.GREETING,
        'expected_skill': None,
        'expected_description': 'Saludo simple',
    },
]
