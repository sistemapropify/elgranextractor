"""Puente fail-open entre el motor de respuestas IA y la memoria conversacional.

El motor (``PromptAssemblyService``) carga el contexto de la conversación desde
``MemoryService`` (app ``intelligence``) para no responder "amnésico". Este
módulo aísla esa integración en helpers pequeños con **fail-open**: si la
memoria falla o no hay identidad disponible, se devuelve ``None``/``{}`` y el
prompt se construye igual que hoy (sin contexto). Nunca rompe producción.

Decisiones de diseño (ver plans/DISENO_CONEXION_MEMORIA_MOTOR_IA.md):
- Identidad: User por ``phone`` del CRM; fallback sintético ``lead:{lead_id}``.
- Aislamiento: ``app_id`` dedicado ``motor-ia-whatsapp`` (AppConfig auto-creado),
  para no contaminar el chat libre ni el respondedor nocturno.
- Sesión: por hilo real (``thread_id``/``id_chatwoot``) cuando esté disponible.
- Resolución de propiedad: mensaje actual → contexto de memoria →
  ``PropertyBotInitialResponse`` (vínculo por phone o external_conversation_id).
"""
import re

PROPERTY_CODE_RE = re.compile(r"\bPROP\s*0*(\d{1,9})\b", re.IGNORECASE)
MOTOR_APP_ID = "motor-ia-whatsapp"


def _normalize_code(raw: str) -> str:
    """Normaliza un código PROP (ej: 'prop 265' -> 'PROP000265')."""
    match = PROPERTY_CODE_RE.search(raw or "")
    if not match:
        return ""
    return f"PROP{int(match.group(1)):06d}"


def _ensure_user(identifier, channel):
    """Crea/obtiene el User de memoria con los campos reales del modelo.

    Evita el bug de ``MemoryService.get_or_create_user`` (asume un campo
    ``level`` inexistente en ``Role`` y no puede crear usuarios nuevos). Se usa
    como fallback solo cuando ese método falla. ``identifier`` es phone o email
    (o sintético ``lead:{id}``); se usa también como ``username`` único.
    """
    from django.db import IntegrityError
    from django.utils import timezone

    from intelligence.models import Role, User

    is_email = "@" in identifier
    role = Role.objects.filter(name="Usuario Básico").first() or Role.objects.first()
    if role is None:
        role = Role.objects.create(
            name="Usuario Básico",
            default_level=1,
            max_level=5,
            default_domains=[],
            capabilities={"memory": True},
            description="Rol por defecto para usuarios nuevos",
        )
    now = timezone.now().isoformat()
    defaults = {
        "role": role,
        "is_active": True,
        "username": identifier,
        "metadata": {"channels": [channel], "first_seen": now, "last_seen": now},
    }
    lookup = {"email": identifier} if is_email else {"phone": identifier}
    try:
        user, _created = User.objects.get_or_create(**lookup, defaults=defaults)
    except IntegrityError:
        # Carrera en threads (check -> create). Reintentar por lectura.
        user = User.objects.get(**lookup)
    return user


def resolve_user(phone, lead_id):
    """Resuelve/crea el User de memoria por phone; fallback ``lead:{id}``.

    Fail-open: sin phone y sin lead_id -> None. No lanza.
    """
    try:
        from intelligence.services.memory import MemoryService

        identifier = str(phone or "").strip()
        if not identifier:
            identifier = f"lead:{lead_id}" if lead_id else ""
        if not identifier:
            return None
        try:
            return MemoryService.get_or_create_user(identifier, channel="whatsapp")
        except Exception:  # noqa: BLE001
            # Bug conocido: get_or_create_user no crea usuarios nuevos porque
            # asume Role.level (inexistente). Fallback con campos reales.
            return _ensure_user(identifier, "whatsapp")
    except Exception:  # noqa: BLE001
        return None


def resolve_session(user, thread_id, app_id=MOTOR_APP_ID):
    """Obtiene la Conversation activa (o la crea) para el user+app+thread."""
    try:
        if user is None:
            return None
        from intelligence.services.memory import MemoryService

        return MemoryService.get_active_session(
            user_id=user.id,
            app_id=app_id,
            session_id=str(thread_id).strip() or None,
        )
    except Exception:  # noqa: BLE001
        return None


def load_context(conversation):
    """Carga el contexto conversacional de la Conversation (fail-open -> {})."""
    try:
        if conversation is None:
            return {}
        from intelligence.services.memory import MemoryService

        return MemoryService.load_conversation_context(conversation.id)
    except Exception:  # noqa: BLE001
        return {}


def resolve_memory(phone, lead_id, thread_id, app_id=MOTOR_APP_ID):
    """Resuelve (user, conversation, context) en una sola pasada fail-open."""
    user = resolve_user(phone, lead_id)
    conversation = resolve_session(user, thread_id, app_id)
    context = load_context(conversation)
    return user, conversation, context


def property_code_from_context(context) -> str:
    """Primer código PROP mencionado en el historial de memoria."""
    messages = (context or {}).get("messages") or []
    for message in messages:
        code = _normalize_code(str(message.get("content") or ""))
        if code:
            return code
    return ""


def property_code_from_initial_response(phone, thread_id) -> str:
    """Fallback: código de la propiedad desde PropertyBotInitialResponse.

    El vínculo con response_intelligence es por hilo (external_conversation_id)
    o por teléfono (no existe lead_id en ese modelo). Fail-open -> "".
    """
    try:
        from n8n_bridge.models import PropertyBotInitialResponse

        qs = PropertyBotInitialResponse.objects.using("default")
        if thread_id:
            qs = qs.filter(external_conversation_id=str(thread_id).strip())
        elif phone:
            qs = qs.filter(phone=str(phone).strip())
        row = qs.order_by("-id").values("property_code", "property_id").first()
        if not row:
            return ""
        if row.get("property_code"):
            return _normalize_code(row["property_code"])
        if row.get("property_id"):
            return f"PROP{int(row['property_id']):06d}"
        return ""
    except Exception:  # noqa: BLE001
        return ""


def save_turn(conversation_id, role, content) -> None:
    """Guarda un turno en memoria (fail-open). ``role``: 'user' | 'assistant'."""
    try:
        if not conversation_id or role not in ("user", "assistant"):
            return
        from intelligence.services.memory import MemoryService

        MemoryService.save_message(conversation_id, role, str(content or ""))
    except Exception:  # noqa: BLE001
        return
