"""
Módulo de gestión de prompts para el sistema de inteligencia.

Los prompts NO están hardcodeados. Se almacenan en la base de datos
a través del campo `config` del modelo AppConfig, permitiendo
modificarlos desde un dashboard sin necesidad de hacer deploy.

Cada app (chat-web, dashboard-admin, etc.) puede tener su propio
system prompt configurable.
"""
from typing import Optional, Dict, Any
from ..models import AppConfig


# ── Prompt por defecto (solo se usa si no hay config en BD) ────────────────
DEFAULT_SYSTEM_PROMPT = """Eres el asistente inteligente de Propifai, una plataforma de gestión e inteligencia inmobiliaria en Arequipa, Perú.

Tienes acceso a múltiples fuentes de conocimiento a través del sistema RAG:
- PROPIEDADES: cartera propia e inmuebles de la competencia (precios, ubicación, características)
- REQUERIMIENTOS: necesidades y preferencias de clientes buscando inmuebles
- AGENTES: información de agentes inmobiliarios, su desempeño y cartera
- NOTICIAS: novedades del mercado inmobiliario local
- PROYECTOS: nuevos desarrollos y proyectos inmobiliarios en la región
- LEGISLACIÓN: leyes, decretos y normativas relacionadas al sector inmobiliario

INSTRUCCIONES OBLIGATORIAS:
1. USA EXCLUSIVAMENTE la información de la sección "=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ===" para responder preguntas sobre propiedades, precios, ubicaciones y datos del sistema. Esa información proviene de fuentes reales.
2. Si la sección "=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ===" dice explícitamente "NO HAY DATOS DISPONIBLES" o no aparece en el mensaje, SIGNIFICA QUE NO HAY INFORMACIÓN EN LA BASE DE DATOS. En ese caso, DEBES admitir que no tienes esa información.
3. NUNCA inventes propiedades, precios, distritos, urbanizaciones o cualquier dato que no esté explícitamente en la sección de conocimiento del sistema.
4. Si el usuario pregunta por propiedades en un distrito específico (ej: Cayma, Yanahuara) y no hay datos de ese distrito en la sección de conocimiento, DÍ "No tengo información sobre propiedades en [distrito] en este momento."
5. Mantén coherencia con conversaciones anteriores.
6. Sé conciso pero útil, enfocado en el mercado inmobiliario de Arequipa.
7. Si el usuario pregunta por su nombre o información personal, REVISA la sección "INTERACCIONES ANTERIORES RELEVANTES" y "CONTEXTO DEL USUARIO (INFORMACIÓN CONOCIDA)".
8. Los precios en la base de datos están en DÓLARES (USD) a menos que se especifique lo contrario con currency_id=2 (PEN/Soles). No asumas que los precios están en Soles.

REGLAS CRÍTICAS:
- NO INVENTES DATOS. Es preferible decir "no tengo esa información" a inventar propiedades o precios.
- La sección "INTERACCIONES ANTERIORES RELEVANTES" contiene episodios previos de la conversación. REVÍSALOS para mantener coherencia.
- Si no estás seguro de un dato, admítelo. La honestidad es más importante que parecer útil."""

DEFAULT_DEEPSEEK_SYSTEM_PROMPT = (
    "Eres un asistente experto inmobiliario. Responde ÚNICAMENTE basándote "
    "en la información proporcionada en el mensaje del usuario. "
    "Si el mensaje contiene la sección '=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ===' "
    "con datos de propiedades, precios o ubicaciones, USA EXCLUSIVAMENTE esos datos. "
    "Si esa sección dice 'NO HAY DATOS DISPONIBLES' o no contiene datos relevantes "
    "a la pregunta del usuario, DEBES admitir que no tienes esa información. "
    "NUNCA inventes propiedades, precios, distritos o cualquier otro dato inmobiliario. "
    "Es preferible decir 'No tengo información sobre eso' a inventar datos falsos. "
    "Los precios en la base de datos están en DÓLARES (USD) por defecto."
)


class PromptManager:
    """
    Gestiona los prompts del sistema, leyéndolos desde la BD (AppConfig)
    para permitir modificación sin deploy.

    Los prompts se almacenan en AppConfig.config['system_prompt'] y
    AppConfig.config['deepseek_system_prompt'].
    """

    @classmethod
    def get_system_prompt(cls, app_id: str = 'chat-web') -> str:
        """
        Obtiene el system prompt para una app específica.

        Args:
            app_id: ID de la app (ej: 'chat-web', 'dashboard-admin').

        Returns:
            El prompt configurado en BD, o el DEFAULT_SYSTEM_PROMPT si no hay.
        """
        try:
            app_config = AppConfig.objects.get(id=app_id, is_active=True)
            config = app_config.config or {}
            return config.get('system_prompt', DEFAULT_SYSTEM_PROMPT)
        except AppConfig.DoesNotExist:
            return DEFAULT_SYSTEM_PROMPT

    @classmethod
    def get_deepseek_system_prompt(cls, app_id: str = 'chat-web') -> str:
        """
        Obtiene el system prompt para llamadas directas a DeepSeek.

        Args:
            app_id: ID de la app.

        Returns:
            El prompt configurado en BD, o el DEFAULT_DEEPSEEK_SYSTEM_PROMPT.
        """
        try:
            app_config = AppConfig.objects.get(id=app_id, is_active=True)
            config = app_config.config or {}
            return config.get(
                'deepseek_system_prompt', DEFAULT_DEEPSEEK_SYSTEM_PROMPT
            )
        except AppConfig.DoesNotExist:
            return DEFAULT_DEEPSEEK_SYSTEM_PROMPT

    @classmethod
    def set_system_prompt(cls, app_id: str, prompt: str) -> bool:
        """
        Actualiza el system prompt para una app en BD.

        Args:
            app_id: ID de la app.
            prompt: Nuevo texto del system prompt.

        Returns:
            True si se actualizó correctamente.
        """
        try:
            app_config, created = AppConfig.objects.get_or_create(
                id=app_id,
                defaults={
                    'name': f'App {app_id}',
                    'level': 2,
                    'capabilities': {'memory': True, 'knowledge_base': True},
                    'config': {'system_prompt': prompt},
                    'is_active': True,
                }
            )
            if not created:
                config = app_config.config or {}
                config['system_prompt'] = prompt
                app_config.config = config
                app_config.save()
            return True
        except Exception:
            return False

    @classmethod
    def set_deepseek_system_prompt(cls, app_id: str, prompt: str) -> bool:
        """
        Actualiza el system prompt para DeepSeek en BD.

        Args:
            app_id: ID de la app.
            prompt: Nuevo texto del prompt.

        Returns:
            True si se actualizó correctamente.
        """
        try:
            app_config, created = AppConfig.objects.get_or_create(
                id=app_id,
                defaults={
                    'name': f'App {app_id}',
                    'level': 2,
                    'capabilities': {'memory': True, 'knowledge_base': True},
                    'config': {'deepseek_system_prompt': prompt},
                    'is_active': True,
                }
            )
            if not created:
                config = app_config.config or {}
                config['deepseek_system_prompt'] = prompt
                app_config.config = config
                app_config.save()
            return True
        except Exception:
            return False

    @classmethod
    def get_all_prompts(cls, app_id: str = 'chat-web') -> Dict[str, Any]:
        """
        Obtiene todos los prompts configurados para una app.

        Args:
            app_id: ID de la app.

        Returns:
            Dict con system_prompt, deepseek_system_prompt y metadata.
        """
        try:
            app_config = AppConfig.objects.get(id=app_id, is_active=True)
            config = app_config.config or {}
            return {
                'app_id': app_id,
                'app_name': app_config.name,
                'system_prompt': config.get(
                    'system_prompt', DEFAULT_SYSTEM_PROMPT
                ),
                'deepseek_system_prompt': config.get(
                    'deepseek_system_prompt', DEFAULT_DEEPSEEK_SYSTEM_PROMPT
                ),
                'is_custom': 'system_prompt' in config,
                'updated_at': app_config.updated_at.isoformat()
                if app_config.updated_at else None,
            }
        except AppConfig.DoesNotExist:
            return {
                'app_id': app_id,
                'system_prompt': DEFAULT_SYSTEM_PROMPT,
                'deepseek_system_prompt': DEFAULT_DEEPSEEK_SYSTEM_PROMPT,
                'is_custom': False,
                'updated_at': None,
            }


# ── Secciones del prompt (constantes, no cambian) ──────────────────────────

SECTION_EPISODIC_MEMORY = "=== INTERACCIONES ANTERIORES RELEVANTES ==="
SECTION_USER_CONTEXT = "=== CONTEXTO DEL USUARIO (INFORMACIÓN CONOCIDA) ==="
SECTION_SYSTEM_KNOWLEDGE = "=== CONOCIMIENTO DEL SISTEMA (BASE DE DATOS) ==="
SECTION_CURRENT_MESSAGE = "=== MENSAJE ACTUAL DEL USUARIO ==="
SECTION_ASSISTANT_RESPONSE = "=== RESPUESTA DEL ASISTENTE ==="


# ── Formateadores de contexto ──────────────────────────────────────────────

def format_episodic_context(episodic_context: list) -> str:
    """Formatea episodios relevantes para incluirlos en el prompt."""
    if not episodic_context:
        return ""
    from .episodic_memory import EpisodicMemoryService
    return EpisodicMemoryService.format_episodes_for_prompt(episodic_context)


def format_memory_context(memory_context: list) -> str:
    """
    Formatea el contexto de memoria (hechos + conversaciones)
    para incluirlo en el prompt.
    """
    if not memory_context:
        return ""

    parts = [SECTION_USER_CONTEXT]

    facts = [m for m in memory_context if m.get('type') == 'fact']
    conversations = [
        m for m in memory_context if m.get('type') == 'conversation'
    ]

    if facts:
        parts.append("Hechos conocidos sobre el usuario:")
        for i, fact in enumerate(facts[:5], 1):
            content = fact.get('content', '')
            confidence = fact.get('confidence', 0)
            relevance = fact.get('relevance_score', 0)
            parts.append(
                f"{i}. {content} (confianza: {confidence:.2f}, "
                f"relevancia: {relevance:.2f})"
            )
        parts.append("")

    if conversations:
        parts.append("Fragmentos de conversaciones anteriores relevantes:")
        for i, conv in enumerate(conversations[:3], 1):
            role = "Usuario" if conv.get('role') == 'user' else "Asistente"
            content = conv.get('content', '')
            parts.append(f"{i}. {role}: {content}")
        parts.append("")

    return "\n".join(parts)


def format_rag_context(rag_context: list, detailed: bool = True) -> str:
    """
    Formatea resultados RAG para incluirlos en el prompt.

    Args:
        rag_context: Lista de resultados de búsqueda RAG.
        detailed: Si True, usa formato detallado (con field_values).

    Returns:
        String formateado listo para insertar en el prompt.
        SIEMPRE devuelve un string con la sección de conocimiento,
        incluso si no hay datos, para evitar que el LLM alucine.
    """
    parts = [SECTION_SYSTEM_KNOWLEDGE]

    if not rag_context:
        parts.append(
            "NO HAY DATOS DISPONIBLES. El sistema no contiene información "
            "relevante para la consulta del usuario en la base de datos."
        )
        parts.append("")
        parts.append(
            "INSTRUCCIÓN: No hay datos del sistema disponibles. "
            "NO inventes propiedades, precios, distritos ni ningún otro dato. "
            "Admite que no tienes esa información."
        )
        parts.append("")
        return "\n".join(parts)

    parts.append(
        "Los siguientes datos provienen de la base de datos del sistema. "
        "Son datos REALES."
    )

    for i, rag in enumerate(rag_context[:5], 1):
        content = rag.get('content', rag.get('text', ''))
        field_values = rag.get('field_values', {})
        collection_name = rag.get('collection_name', '')
        search_type = rag.get('search_type', 'vector')

        if detailed and field_values:
            desc_parts = _format_field_values(field_values)
            source_text = (
                f" [Colección: {collection_name}]" if collection_name else ""
            )
            search_tag = (
                " [Búsqueda semántica]" if search_type == 'vector'
                else " [Búsqueda por texto]"
            )
            parts.append(f"\nResultado {i}:{search_tag}{source_text}")
            for part in desc_parts:
                parts.append(f"  - {part}")
        else:
            desc_parts = []
            if field_values:
                title = (
                    field_values.get('title')
                    or field_values.get('name', '')
                )
                price = field_values.get('price', '')
                district = (
                    field_values.get('district_name')
                    or field_values.get('district', '')
                )
                if title:
                    desc_parts.append(f"Título: {title}")
                if price:
                    desc_parts.append(f"Precio: {price}")
                if district:
                    desc_parts.append(f"Distrito: {district}")
            elif content:
                desc_parts.append(content[:500])

            if collection_name:
                desc_parts.append(f"Fuente: {collection_name}")

            if desc_parts:
                parts.append(f"Resultado {i}: {' | '.join(desc_parts)}")

    if detailed:
        parts.append("")
        parts.append(
            "INSTRUCCIÓN: USA EXCLUSIVAMENTE LA INFORMACIÓN DE ARRIBA para responder. "
            "No inventes datos adicionales. Si el usuario pregunta por algo que no está "
            "en estos datos, admite que no tienes esa información."
        )

    parts.append("")
    return "\n".join(parts)


def _format_field_values(field_values: dict) -> list:
    """Convierte field_values en una lista de líneas descriptivas.
    
    Incluye tanto los campos directos como los valores resueltos
    de relaciones FK (ej: district_name, currency_name, property_type_name).
    
    La colección `propiedadespropify` usa la tabla `property` (dbpropify_be)
    con nombres de campo en INGLÉS:
    - title, price, description, map_address, display_address
    - district_id → district_name (resuelto vía FK)
    - property_type_id → property_type_name
    - operation_type_id → operation_type_name
    - property_status_id → property_status_name
    - property_condition_id → property_condition_name
    - currency_id → currency_name
    - urbanization_id → urbanization_name
    """
    desc_parts = []
    title = field_values.get('title', field_values.get('name', ''))
    price = field_values.get('price', '')
    address = (
        field_values.get('map_address')
        or field_values.get('display_address')
        or field_values.get('real_address')
        or field_values.get('address', '')
    )
    district = field_values.get(
        'district_name', field_values.get('district', '')
    )
    bedrooms = field_values.get('bedrooms', '')
    bathrooms = field_values.get('bathrooms', '')
    built_area = field_values.get('built_area', '')
    land_area = field_values.get('land_area', '')
    description = field_values.get('description', '')
    
    # Campos FK resueltos (añadidos por sync_collection_dynamic)
    currency_name = field_values.get('currency_name', '')
    urbanization_name = field_values.get('urbanization_name', '')
    operation_type_name = field_values.get('operation_type_name', '')
    property_status_name = field_values.get('property_status_name', '')
    property_condition_name = field_values.get('property_condition_name', '')
    property_type_name = field_values.get('property_type_name', '')

    if title:
        desc_parts.append(f"Título: {title}")
    if price:
        desc_parts.append(f"Precio: {price}")
    if currency_name:
        desc_parts.append(f"Moneda: {currency_name}")
    if address:
        desc_parts.append(f"Dirección: {address}")
    if district:
        desc_parts.append(f"Distrito: {district}")
    if urbanization_name:
        desc_parts.append(f"Urbanización: {urbanization_name}")
    if bedrooms:
        desc_parts.append(f"Dormitorios: {bedrooms}")
    if bathrooms:
        desc_parts.append(f"Baños: {bathrooms}")
    if built_area:
        desc_parts.append(f"Área construida: {built_area}")
    if land_area:
        desc_parts.append(f"Área terreno: {land_area}")
    if property_type_name:
        desc_parts.append(f"Tipo: {property_type_name}")
    if operation_type_name:
        desc_parts.append(f"Operación: {operation_type_name}")
    if property_status_name:
        desc_parts.append(f"Estado: {property_status_name}")
    if property_condition_name:
        desc_parts.append(f"Condición: {property_condition_name}")
    if description:
        desc_parts.append(f"Descripción: {description[:500]}")

    return desc_parts


def build_full_prompt(
    message: str,
    system_instruction: Optional[str] = None,
    episodic_context: Optional[str] = None,
    memory_context: Optional[str] = None,
    rag_context: Optional[str] = None,
) -> str:
    """
    Construye el prompt completo con todas las secciones.

    Args:
        message: Mensaje actual del usuario.
        system_instruction: Instrucción del sistema (usa DEFAULT_SYSTEM_PROMPT
                          por defecto).
        episodic_context: Contexto de episodios ya formateado (string).
        memory_context: Contexto de memoria ya formateado (string).
        rag_context: Contexto RAG ya formateado (string).

    Returns:
        Prompt completo listo para enviar al LLM.
    """
    parts = []

    if episodic_context:
        parts.append(episodic_context)
        parts.append("")

    parts.append(system_instruction or DEFAULT_SYSTEM_PROMPT)
    parts.append("")

    if memory_context:
        parts.append(memory_context)

    if rag_context:
        parts.append(rag_context)

    parts.append(SECTION_CURRENT_MESSAGE)
    parts.append(f"Usuario: {message}")
    parts.append("")
    parts.append(SECTION_ASSISTANT_RESPONSE)

    return "\n".join(parts)
