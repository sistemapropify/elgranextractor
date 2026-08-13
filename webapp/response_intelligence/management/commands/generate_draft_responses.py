"""Genera borradores de respuesta del motor IA (sandbox / shadow / production).

Uso:
    python manage.py generate_draft_responses --mode=sandbox --date_from=YYYY-MM-DD --date_to=YYYY-MM-DD

Nivel 1 (sandbox): genera drafts sobre conversaciones históricas sin enviar nada.
El CRM se lee solo con SELECT; los drafts se persisten en la BD ``default``.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from intelligence.learning.trace_context import bind_trace_id, release_trace_id
from intelligence.services.llm import LLMService
from lead_intelligence.conversation_analysis import analyze_chat_history
from lead_intelligence.services import _lead_result_rows

from response_intelligence.curation import CurationService
from response_intelligence import memory_bridge
from response_intelligence.models import BotResponseDraft
from response_intelligence.prompt_assembly import PromptAssemblyService

PROPERTY_CODE_RE = re.compile(r"\bPROP\d{6,9}\b", re.IGNORECASE)


class Command(BaseCommand):
    help = (
        "Genera borradores de respuesta del motor IA (few-shot + RAG) para "
        "conversaciones de leads. mode=sandbox no envía nada a WhatsApp."
    )

    def add_arguments(self, parser):
        parser.add_argument("--mode", default="sandbox", choices=["sandbox", "shadow_live", "production"])
        parser.add_argument("--date_from", dest="date_from")
        parser.add_argument("--date_to", dest="date_to")
        parser.add_argument("--lead-id", type=int)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--all-messages", action="store_true", help="Genera un draft por cada mensaje de cliente después del primero.")
        parser.add_argument("--dry-run", action="store_true")

    @staticmethod
    def _property_code_from_messages(messages) -> str:
        for message in messages:
            match = PROPERTY_CODE_RE.search(str(message.get("text") or ""))
            if match:
                return match.group(0).upper()
        return ""

    @staticmethod
    def _process_lead(row, *, mode, all_messages, dry_run):
        close_old_connections()
        analysis = analyze_chat_history(row["chat_history"])
        messages = analysis.get("messages") or []
        client_messages = [m for m in messages if m.get("sender") == "lead"]
        # El primer mensaje lo responde el bot determinista de plantillas:
        # el motor IA interviene desde el segundo mensaje del lead.
        targets = client_messages[1:] if all_messages else (client_messages[1:2] or [])
        if not targets:
            return row["id"], "skipped"

        from response_intelligence.guardrails import (
            block_summary,
            is_escalation,
            validate_generated_response,
        )

        property_code = Command._property_code_from_messages(messages)
        created = 0
        escalations = 0
        for target in targets:
            text = str(target.get("text") or "").strip()
            if not text:
                continue
            intent_category = CurationService._detect_category(text)

            # Guardrail (spec §7): escalamiento nunca genera con IA.
            if is_escalation(text):
                if not dry_run:
                    draft = BotResponseDraft.objects.using("default").create(
                        source_lead_id=row["id"],
                        client_message=text,
                        intent_category=intent_category,
                        prompt_snapshot={"guardrail": "escalamiento"},
                        generated_response="",
                        property_data_used=[],
                        mode=mode,
                        model_version=LLMService.DEEPSEEK_MODEL,
                        trace_id=f"bot_draft:{0}",
                        auto_escalation=True,
                        blocked_reason="Mensaje de escalamiento/riesgo legal: la plantilla responde con aviso a agente",
                    )
                    draft.trace_id = f"bot_draft:{draft.pk}"
                    draft.save(using="default", update_fields=["trace_id"])
                escalations += 1
                continue

            assembled = PromptAssemblyService.assemble(
                client_message=text,
                intent_category=intent_category,
                property_code=property_code,
                lead_id=row["id"],
                phone=row.get("phone"),
                thread_id=row.get("id_chatwoot"),
            )
            memory_id = (assembled.get("memory") or {}).get("conversation_id")
            if dry_run:
                created += 1
                continue

            # Escribir el turno del cliente en memoria (sandbox y production;
            # shadow_live es solo lectura: el borrador no se envía).
            if memory_id and mode in ("sandbox", "production"):
                memory_bridge.save_turn(memory_id, "user", text)

            draft = BotResponseDraft.objects.using("default").create(
                source_lead_id=row["id"],
                client_message=text,
                intent_category=assembled["intent_category"] or intent_category,
                prompt_snapshot={
                    "system_prompt": assembled["system_prompt"],
                    "user_prompt": assembled["user_prompt"],
                    "few_shot": assembled["few_shot"],
                    # Contexto del lead/hilo para que el revisor sepa el origen.
                    "context": {
                        "thread_id": row.get("id_chatwoot"),
                        "phone": row.get("phone"),
                    },
                },
                generated_response="",
                property_data_used=assembled["property_data_used"],
                mode=mode,
                model_version=LLMService.DEEPSEEK_MODEL,
                trace_id=f"bot_draft:{0}",  # se corrige tras crear con el id real
            )
            trace_token = bind_trace_id(f"bot_draft:{draft.pk}")
            try:
                ok, msg, response = LLMService.generate_response(
                    system_prompt=assembled["system_prompt"],
                    user_prompt=assembled["user_prompt"],
                    max_tokens=600,
                )
            finally:
                release_trace_id(trace_token)
            if not ok:
                draft.generated_response = ""
                draft.trace_id = f"bot_draft:{draft.pk}"
                draft.save(using="default", update_fields=["trace_id"])
                continue
            draft.generated_response = response
            draft.trace_id = f"bot_draft:{draft.pk}"
            # En production, la respuesta es la que se envía: se guarda también
            # en memoria para que el siguiente turno tenga contexto completo.
            if mode == "production" and memory_id:
                memory_bridge.save_turn(memory_id, "assistant", response)
            # Validación determinista post-generación (spec §7).
            validation = validate_generated_response(
                response, draft.property_data_used
            )
            draft.auto_hallucination = validation["hallucination"]
            draft.auto_discount = validation["discount"]
            if validation["blocked"]:
                draft.blocked_reason = block_summary(validation)
            draft.save(
                using="default",
                update_fields=[
                    "generated_response",
                    "trace_id",
                    "auto_hallucination",
                    "auto_discount",
                    "blocked_reason",
                ],
            )
            created += 1
        detail = f"created={created}"
        if escalations:
            detail += f", escalamientos={escalations}"
        return row["id"], detail

    def handle(self, *args, **options):
        mode = options["mode"]
        lead_id = options["lead_id"]
        date_from = options["date_from"]
        date_to = options["date_to"]
        if lead_id:
            rows = _lead_result_rows(None, None, lead_id=lead_id)
        else:
            if not date_from or not date_to:
                raise CommandError("Indica --date_from y --date_to, o --lead-id.")
            rows = _lead_result_rows(
                __import__("datetime").date.fromisoformat(date_from),
                __import__("datetime").date.fromisoformat(date_to),
            )
        if options["limit"] > 0:
            rows = rows[: options["limit"]]
        workers = min(max(options["workers"], 1), 8)

        total = created_total = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._process_lead,
                    row,
                    mode=mode,
                    all_messages=options["all_messages"],
                    dry_run=options["dry_run"],
                ): row
                for row in rows
            }
            for future in as_completed(futures):
                total += 1
                _lead_id, detail = future.result()
                self.stdout.write(f"Lead #{_lead_id}: {detail}")
                if detail.startswith("created="):
                    created_total += int(detail.split("=")[1])

        self.stdout.write(
            self.style.SUCCESS(
                f"Leads procesados: {total} · drafts creados: {created_total} · modo={mode}"
            )
        )
