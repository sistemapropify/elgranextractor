"""Ensamblado del prompt para el motor de respuestas IA (few-shot + RAG).

Reglas de negocio + ejemplos curados + datos de propiedad en vivo (SELECT al CRM)
+ historial de la conversación. Todo lo nuevo se persiste en la BD ``default``.
"""

import re

from n8n_bridge.services.initial_property_detector import extract_property_identity

from . import memory_bridge
from .curation import CurationService
from .models import BusinessRule, CuratedExample


class PromptAssemblyService:
    """Construye el prompt final y audita qué se inyectó (prompt_snapshot)."""

    MAX_FEW_SHOT = 6

    # ------------------------------------------------------------------ #
    # Reglas y tono
    # ------------------------------------------------------------------ #
    @classmethod
    def build_system_prompt(cls) -> str:
        """Prompt de sistema con las reglas de negocio activas + tono."""
        rules = list(
            BusinessRule.objects.using("default")
            .filter(active=True)
            .order_by("category", "id")
        )
        sections = []
        for category, label in (
            ("prohibicion", "PROHIBIDO"),
            ("tono", "TONO Y ESTILO"),
            ("escalamiento", "ESCALAMIENTO"),
        ):
            texts = [r.rule_text.strip() for r in rules if r.category == category]
            if texts:
                lines = "\n".join(f"- {t}" for t in texts)
                sections.append(f"[{label}]\n{lines}")

        base = (
            "Eres el asistente nocturno de una inmobiliaria en Arequipa, Perú. "
            "Respondes SOLO en español, con tono cercano y profesional, sin "
            "prometer nada que no esté respaldado por los datos de la propiedad "
            "proporcionados. Si no tienes el dato, no lo inventes: di que un "
            "asesor te dará la información exacta en horario de atención."
        )
        if sections:
            base += "\n\n" + "\n\n".join(sections)
        return base

    # ------------------------------------------------------------------ #
    # Selección de ejemplos few-shot
    # ------------------------------------------------------------------ #
    @classmethod
    def _keyword_overlap(cls, text: str, candidate: str) -> int:
        tokens = set(re.findall(r"[\wáéíóúñ]+", (text or "").lower()))
        cand_tokens = set(re.findall(r"[\wáéíóúñ]+", (candidate or "").lower()))
        return len(tokens & cand_tokens)

    @classmethod
    def select_few_shot(cls, client_message: str, intent_category: str = "", k: int = MAX_FEW_SHOT) -> list:
        """Selecciona los k ejemplos aprobados y activos más relevantes.

        Prioriza la categoría de intención detectada y luego el solape de
        palabras clave con el mensaje del cliente. Sin embeddings para arrancar.
        """
        if intent_category not in CuratedExample.IntentCategory.values:
            intent_category = CurationService._detect_category(client_message)
        base_qs = (
            CuratedExample.objects.using("default")
            .filter(approved=True, active=True)
            .order_by("-updated_at")
        )
        same_category = list(
            base_qs.filter(intent_category=intent_category)[: k * 3]
        )
        if len(same_category) < k:
            seen = {e.pk for e in same_category}
            others = [
                e
                for e in base_qs[: k * 6]
                if e.pk not in seen
            ]
            same_category.extend(others)
        ranked = sorted(
            same_category,
            key=lambda e: cls._keyword_overlap(client_message, e.client_message),
            reverse=True,
        )
        return ranked[:k]

    # ------------------------------------------------------------------ #
    # Datos de propiedad en vivo (reutiliza el SELECT del bot de plantillas)
    # ------------------------------------------------------------------ #
    @staticmethod
    def fetch_live_property_data(property_code: str) -> dict:
        """Consulta la propiedad en vivo (SELECT al CRM), como el bot de plantillas."""
        from intelligence.skills.propiedades.informacion_inicial_propiedad import (
            InformacionInicialPropiedadSkill,
        )

        result = InformacionInicialPropiedadSkill().execute(
            {"property_code": property_code}
        )
        if not result.success:
            return {"success": False, "reason_code": (result.metadata or {}).get("reason_code", "ERROR")}
        return {"success": True, "data": result.data}

    # ------------------------------------------------------------------ #
    # Ensamblado final
    # ------------------------------------------------------------------ #
    @classmethod
    def assemble(
        cls,
        client_message: str,
        intent_category: str = "",
        property_code: str = "",
        *,
        lead_id=None,
        phone=None,
        thread_id=None,
        app_id="motor-ia-whatsapp",
        conversation_messages=None,
    ) -> dict:
        """Compone el prompt final y devuelve lo inyectado para auditoría.

        Incorpora el contexto conversacional real (memoria de la app
        ``intelligence``) para no responder "amnésico". Si ``property_code`` no
        llega, se resuelve en este orden: mensaje actual -> contexto de memoria
        -> PropertyBotInitialResponse. Todo es fail-open: si la memoria no está
        disponible, el prompt se arma igual que antes (sin contexto).

        Devuelve:
        {
          "system_prompt": str,
          "user_prompt": str,
          "few_shot": [{"client_message","agent_response"}, ...],
          "property_data_used": [dict, ...] | [],
          "intent_category": str,
          "memory": {"conversation_id", "user_id", "app_id"},  # write-path
        }
        """
        system_prompt = cls.build_system_prompt()
        few_shot = cls.select_few_shot(client_message, intent_category)

        # Memoria conversacional (fail-open: contexto vacío si no se puede).
        user, conversation, context = memory_bridge.resolve_memory(
            phone, lead_id, thread_id, app_id
        )

        # Un código explícito en el mensaje actual siempre cambia el contexto.
        detected = extract_property_identity(client_message)
        if detected.get("codes"):
            property_code = detected["codes"][0]
        elif not property_code:
            property_code = memory_bridge.property_code_from_context(context)
            if not property_code:
                property_code = memory_bridge.property_code_from_initial_response(
                    phone, thread_id
                )

        property_data_used = []
        if property_code:
            live = cls.fetch_live_property_data(property_code)
            if live.get("success"):
                property_data_used.append(live["data"])

        # Bloque de ejemplo few-shot (solo si hay ejemplos aprobados).
        examples_block = ""
        if few_shot:
            rendered = []
            for example in few_shot:
                rendered.append(
                    "CLIENTE: {c}\nASISTENTE: {a}".format(
                        c=example.client_message, a=example.agent_response
                    )
                )
            examples_block = (
                "\n\nEjemplos de respuestas correctas (tono y estructura a seguir):\n"
                + "\n\n".join(rendered)
            )

        # En shadow_live se usa lead -> respuesta sombra, sin respuestas humanas.
        # La memoria normal se conserva para los demás modos.
        conversation_block = ""
        if conversation_messages is not None:
            lines = []
            for message in conversation_messages[-16:]:
                role_label = (
                    "Cliente"
                    if message.get("role") == "user"
                    else "Asistente sombra"
                )
                content = str(message.get("content") or "").strip()
                if content:
                    lines.append(f"{role_label}: {content}")
            if lines:
                conversation_block = (
                    "\n\nContexto de la conversación sombra (continúa este hilo; "
                    "no repitas saludos ni vuelvas a pedir datos ya presentes):\n"
                    + "\n".join(lines)
                )
        elif context:
            lines = []
            for message in (context.get("messages") or [])[-6:]:
                role_label = (
                    "Cliente" if message.get("role") == "user" else "Asistente"
                )
                content = str(message.get("content") or "").strip()
                if content:
                    lines.append(f"{role_label}: {content}")
            summary = str(context.get("summary") or "").strip()
            if lines or summary:
                parts = []
                if lines:
                    parts.append("\n".join(lines))
                if summary:
                    parts.append(f"Resumen previo: {summary}")
                conversation_block = (
                    "\n\nContexto de la conversación (historial previo, úsalo "
                    "para mantener coherencia):\n" + "\n\n".join(parts)
                )

        # Bloque de datos de la propiedad (RAG).
        property_block = ""
        if property_data_used:
            data = property_data_used[0]
            lines = [
                f"- Código: {data.get('code', '')}",
                f"- Título: {data.get('title', '')}",
                f"- Tipo: {data.get('property_type', '')}",
                f"- Ubicación: {data.get('location', '')}",
            ]
            price = data.get("price") or {}
            lines.append(
                "- Precio: {amount} {currency}".format(
                    amount=price.get("amount", "—"),
                    currency=price.get("currency", ""),
                )
            )
            for feature in (data.get("features") or []):
                lines.append(f"- {feature.get('field', '')}: {feature.get('value', '')}")
            property_block = (
                "\n\nDatos verificados de la propiedad consultada (NO inventes "
                "datos fuera de esta lista):\n" + "\n".join(lines)
            )

        user_prompt = (
            "El cliente escribe:\n"
            f"{client_message}\n"
            f"{examples_block}{conversation_block}{property_block}\n\n"
            "Responde de forma natural, breve y en español."
        )
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "few_shot": [
                {"client_message": e.client_message, "agent_response": e.agent_response}
                for e in few_shot
            ],
            "property_data_used": property_data_used,
            "intent_category": intent_category,
            "memory": {
                "conversation_id": str(conversation.id) if conversation else None,
                "user_id": str(user.id) if user else None,
                "app_id": app_id,
            },
        }
