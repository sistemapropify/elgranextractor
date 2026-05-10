"""
Clasificador de intención del mensaje del usuario.

Determina qué tipo de consulta está haciendo el usuario usando reglas
basadas en palabras clave. Esto permite optimizar el flujo:
- Si es un saludo, no buscar RAG ni memoria episódica
- Si es búsqueda de propiedades, priorizar RAG
- Si pregunta por sí mismo, priorizar memoria

Sin LLM, sin embeddings — rápido y determinístico.
"""
import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


class IntentType(Enum):
    """Tipos de intención detectables."""
    GREETING = "saludo"
    FAREWELL = "despedida"
    THANKS = "agradecimiento"
    PROPERTY_SEARCH = "busqueda_propiedades"
    REQUIREMENT_SEARCH = "busqueda_requerimientos"
    PRICE_QUERY = "consulta_precio"
    USER_INFO = "informacion_usuario"
    MARKET_QUERY = "consulta_mercado"
    LEGAL_QUERY = "consulta_legal"
    PROJECT_QUERY = "consulta_proyectos"
    AGENT_QUERY = "consulta_agentes"
    HELP = "ayuda"
    GENERAL = "consulta_general"
    UNKNOWN = "no_detectada"


@dataclass
class IntentResult:
    """Resultado del clasificador de intención."""
    intent: IntentType = IntentType.UNKNOWN
    confidence: float = 0.0
    extracted_params: Dict[str, any] = field(default_factory=dict)
    skip_rag: bool = False
    skip_memory: bool = False
    skip_episodic: bool = False
    requires_rag: bool = False
    requires_memory: bool = False


class IntentClassifier:
    """
    Clasifica la intención del mensaje usando reglas + keywords.
    Sin LLM, sin embeddings — rápido y determinístico.

    Cada regla define:
    - keywords: palabras que activan la intención
    - entities: entidades del dominio inmobiliario
    - skip_rag: si se puede omitir búsqueda RAG
    - skip_memory: si se puede omitir memoria
    - skip_episodic: si se pueden omitir episodios
    - requires_rag: si es obligatorio buscar RAG
    - requires_memory: si es obligatorio buscar memoria
    """

    # ── Palabras clave por tipo de intención ───────────────────────────────

    RULES: Dict[IntentType, Dict] = {
        IntentType.GREETING: {
            'keywords': [
                'hola', 'buenos días', 'buenas tardes', 'buenas noches',
                'hey', 'qué tal', 'que tal', 'buen día', 'buena tarde',
                'buena noche', 'saludos', 'hello', 'hi',
            ],
            'skip_rag': True,
            'skip_memory': True,
            'skip_episodic': True,
            'requires_rag': False,
            'requires_memory': False,
            'priority': 10,  # Alta prioridad
        },
        IntentType.FAREWELL: {
            'keywords': [
                'adiós', 'adios', 'chao', 'bye', 'nos vemos', 'hasta luego',
                'hasta pronto', 'que tengas buen', 'cuídate', 'cuidate',
            ],
            'skip_rag': True,
            'skip_memory': True,
            'skip_episodic': True,
            'requires_rag': False,
            'requires_memory': False,
            'priority': 10,
        },
        IntentType.THANKS: {
            'keywords': [
                'gracias', 'muchas gracias', 'te agradezco', 'thanks',
                'thank you', 'muy amable', 'excelente', 'perfecto',
            ],
            'skip_rag': True,
            'skip_memory': True,
            'skip_episodic': True,
            'requires_rag': False,
            'requires_memory': False,
            'priority': 10,
        },
        IntentType.HELP: {
            'keywords': [
                'ayuda', 'help', 'qué puedes hacer', 'que puedes hacer',
                'cómo funciona', 'como funciona', 'capacidades',
                'qué sabes', 'que sabes', 'comandos',
            ],
            'skip_rag': True,
            'skip_memory': True,
            'skip_episodic': True,
            'requires_rag': False,
            'requires_memory': False,
            'priority': 8,
        },
        IntentType.PROPERTY_SEARCH: {
            'keywords': [
                'busca', 'encuentra', 'quiero', 'necesito', 'hay',
                'mostrar', 'lista', 'encuentro', 'buscar', 'encuentre',
                'quisiera', 'me interesa', 'estoy buscando',
            ],
            'entities': [
                'casa', 'departamento', 'terreno', 'local', 'oficina',
                'propiedad', 'propiedades', 'inmueble', 'vivienda', 'lote', 'piso',
                'suite', 'penthouse', 'dúplex', 'duplex', 'loft',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 7,
        },
        IntentType.REQUIREMENT_SEARCH: {
            'keywords': [
                'requerimiento', 'cliente busca', 'cliente quiere',
                'demanda', 'comprador', 'inquilino', 'arrendatario',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 7,
        },
        IntentType.PRICE_QUERY: {
            'keywords': [
                'precio', 'cuánto cuesta', 'cuanto cuesta', 'cuánto vale',
                'cuanto vale', 'valor', 'precios', 'costos', 'costo',
                'precio promedio', 'precio por m2', 'precio m2',
                'precio por metro cuadrado', 'metro cuadrado', 'metros cuadrados', 'm2',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 6,
        },
        IntentType.USER_INFO: {
            'keywords': [
                'mi nombre', 'quién soy', 'quien soy', 'cómo me llamo',
                'como me llamo', 'mis datos', 'mi información',
                'recuerdas quién', 'sabes quién',
            ],
            'skip_rag': True,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': False,
            'requires_memory': True,
            'priority': 6,
        },
        IntentType.MARKET_QUERY: {
            'keywords': [
                'mercado', 'tendencia', 'análisis', 'analisis',
                'estadística', 'estadistica', 'indicador',
                'comportamiento', 'evolución', 'evolucion',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 5,
        },
        IntentType.LEGAL_QUERY: {
            'keywords': [
                'ley', 'decreto', 'normativa', 'reglamento', 'legal',
                'impuesto', 'tributo', 'alcabala', 'predial',
                'municipal', 'municipio', 'permiso', 'licencia',
                'legislación', 'legislacion',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 5,
        },
        IntentType.PROJECT_QUERY: {
            'keywords': [
                'proyecto', 'nuevo desarrollo', 'constructora',
                'edificio', 'condominio', 'urbanización', 'urbanizacion',
                'en construcción', 'en construccion', 'planos',
                'proyecto inmobiliario',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 5,
        },
        IntentType.AGENT_QUERY: {
            'keywords': [
                'agente', 'corredor', 'inmobiliario', 'vendedor',
                'asesor', 'broker', 'agentes',
            ],
            'skip_rag': False,
            'skip_memory': False,
            'skip_episodic': False,
            'requires_rag': True,
            'requires_memory': False,
            'priority': 5,
        },
    }

    # ── Zonas/distritos de Arequipa para extraer ───────────────────────────
    ZONAS_AREQUIPA = [
        'cayma', 'yanahuara', 'cercado', 'miraflores',
        'jose luis bustamante', 'bustamante', 'sachaca',
        'cerro colorado', 'mariano melgar', 'paucarpata',
        'socabaya', 'tiabaya', 'sabandia', 'characato',
        'yura', 'ucheumayo', 'polobaya', 'quequeña',
        'mollebaya', 'la joya', 'vitor', 'santa isabel de siguas',
        'cayma alta', 'cayma baja', 'umacollo', 'vallecito',
        'selva alegre', 'tahuaycani', 'larsen',
    ]

    # ── Tipos de propiedad para extraer ────────────────────────────────────
    TIPOS_PROPIEDAD = [
        'casa', 'departamento', 'terreno', 'local comercial',
        'oficina', 'lote', 'vivienda', 'suite', 'penthouse',
        'duplex', 'dúplex', 'loft', 'local',
    ]

    # ── Monedas para extraer ───────────────────────────────────────────────
    MONEDAS = {
        'soles': 'PEN', 'sol': 'PEN', 's/.': 'PEN', 's/': 'PEN',
        'dólares': 'USD', 'dolar': 'USD', 'dolares': 'USD',
        'usd': 'USD', '$': 'USD',
    }

    @classmethod
    def classify(cls, message: str) -> IntentResult:
        """
        Clasifica la intención del mensaje del usuario.

        Args:
            message: Mensaje del usuario.

        Returns:
            IntentResult con la intención detectada y parámetros extraídos.
        """
        message_lower = message.lower().strip()

        if not message_lower:
            return IntentResult(intent=IntentType.UNKNOWN, confidence=0.0)

        # Extraer parámetros primero (zonas, tipos, precios)
        extracted_params = cls._extract_parameters(message_lower)

        # Evaluar todas las reglas
        best_result = IntentResult(
            intent=IntentType.GENERAL,
            confidence=0.1,  # Default bajo, cualquier match de keyword lo supera
            extracted_params=extracted_params,
            skip_rag=False,
            skip_memory=False,
            skip_episodic=False,
            requires_rag=False,
            requires_memory=False,
        )

        for intent_type, rule in cls.RULES.items():
            score = cls._evaluate_rule(message_lower, rule)

            if score > best_result.confidence:
                best_result = IntentResult(
                    intent=intent_type,
                    confidence=score,
                    extracted_params=extracted_params,
                    skip_rag=rule.get('skip_rag', False),
                    skip_memory=rule.get('skip_memory', False),
                    skip_episodic=rule.get('skip_episodic', False),
                    requires_rag=rule.get('requires_rag', False),
                    requires_memory=rule.get('requires_memory', False),
                )

        # ── Corrección: si el mensaje menciona zonas o tipos de propiedad ──
        # Aunque la intención sea GREETING (saludo), si el usuario preguntó
        # por una zona/distrito o tipo de propiedad, NO saltarse el RAG.
        # Ej: "hola me podrias decir si tienes propiedades en cayma"
        #      → GREETING con skip_rag=True, pero "cayma" está en zonas.
        has_zones = bool(extracted_params.get('zonas'))
        has_property_types = bool(extracted_params.get('tipos_propiedad'))
        if has_zones or has_property_types:
            best_result.skip_rag = False
            best_result.requires_rag = True

        return best_result

    @classmethod
    def _evaluate_rule(cls, message: str, rule: Dict) -> float:
        """
        Evalúa qué tan bien coincide un mensaje con una regla.

        Returns:
            Puntaje de 0.0 a 1.0.
        """
        score = 0.0
        keywords = rule.get('keywords', [])
        entities = rule.get('entities', [])
        priority = rule.get('priority', 1)

        # Evaluar keywords
        for kw in keywords:
            if kw in message:
                score += 0.3
                break  # Solo una vez por keyword match

        # Evaluar entidades (si aplica)
        if entities:
            for entity in entities:
                if entity in message:
                    score += 0.2
                    break

        # Bonus por longitud del mensaje (mensajes muy cortos
        # como "hola" tienen alta probabilidad de ser saludo).
        # Solo aplica si NO hay entidades (evita falsos positivos
        # como "alquiler de departamento" clasificado como saludo).
        word_count = len(message.split())
        if word_count <= 2 and priority >= 8 and not entities:
            score += 0.2
        elif word_count <= 3 and priority >= 8 and not entities:
            score += 0.1

        # Normalizar por prioridad
        score = min(score * (priority / 10), 1.0)

        return score

    @classmethod
    def _extract_parameters(cls, message: str) -> Dict:
        """
        Extrae parámetros estructurados del mensaje.

        Returns:
            Dict con zonas, tipos_propiedad, moneda, rango_precio, etc.
        """
        params: Dict = {
            'zonas': [],
            'tipos_propiedad': [],
            'moneda': None,
            'rango_precio': None,
            'dormitorios': None,
            'operacion': None,  # venta, alquiler
        }

        # Extraer zonas
        for zona in cls.ZONAS_AREQUIPA:
            if zona in message:
                params['zonas'].append(zona)

        # Extraer tipos de propiedad
        for tipo in cls.TIPOS_PROPIEDAD:
            if tipo in message:
                params['tipos_propiedad'].append(tipo)

        # Extraer moneda
        for moneda_str, moneda_code in cls.MONEDAS.items():
            if moneda_str in message:
                params['moneda'] = moneda_code
                break

        # Extraer operación
        if any(w in message for w in ['alquiler', 'alquilar', 'renta', 'rentar']):
            params['operacion'] = 'alquiler'
        elif any(w in message for w in ['venta', 'comprar', 'compra']):
            params['operacion'] = 'venta'

        # Extraer número de dormitorios
        dorm_match = re.search(
            r'(\d+)\s*(dormitorio|habitacion|hab|cuarto|dorm)',
            message
        )
        if dorm_match:
            params['dormitorios'] = int(dorm_match.group(1))

        # Extraer rango de precio
        price_match = re.search(
            r'(?:de|entre|desde|hasta|menos de|más de|mas de)\s*'
            r'(\d+[\d,]*)\s*(?:a|-)?\s*(\d+[\d,]*)?',
            message
        )
        if price_match:
            params['rango_precio'] = {
                'min': price_match.group(1).replace(',', ''),
                'max': price_match.group(2).replace(',', '')
                if price_match.group(2) else None,
            }

        return params

    @classmethod
    def should_skip_rag(cls, message: str) -> bool:
        """Atajo: determina si se puede omitir RAG para este mensaje."""
        result = cls.classify(message)
        return result.skip_rag

    @classmethod
    def should_skip_memory(cls, message: str) -> bool:
        """Atajo: determina si se puede omitir memoria para este mensaje."""
        result = cls.classify(message)
        return result.skip_memory

    @classmethod
    def should_skip_episodic(cls, message: str) -> bool:
        """Atajo: determina si se pueden omitir episodios."""
        result = cls.classify(message)
        return result.skip_episodic

    @classmethod
    def needs_rag(cls, message: str) -> bool:
        """Atajo: determina si es OBLIGATORIO buscar RAG."""
        result = cls.classify(message)
        return result.requires_rag

    @classmethod
    def needs_memory(cls, message: str) -> bool:
        """Atajo: determina si es OBLIGATORIO buscar memoria."""
        result = cls.classify(message)
        return result.requires_memory
