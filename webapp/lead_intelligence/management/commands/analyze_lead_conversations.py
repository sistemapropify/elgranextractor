import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from django.utils import timezone

from intelligence.services.llm import LLMService
from intelligence.skills.analizar_conversacion_lead import (
    AnalizarConversacionLeadSkill,
)
from lead_intelligence.contextual_analysis import (
    ANALYSIS_VERSION,
    conversation_hash,
)
from lead_intelligence.conversation_analysis import analyze_chat_history
from lead_intelligence.models import (
    AnalysisRun,
    AnalysisRunStep,
    LeadConversationAssessment,
)
from lead_intelligence.services import _lead_result_rows


# Señal de cancelación cooperativa: el dashboard puede pedir detener una
# ejecución en curso sin matar el proceso (corta el gasto de tokens).
_cancel_event = threading.Event()


def request_cancel():
    _cancel_event.set()


def reset_cancel():
    _cancel_event.clear()


def is_cancel_requested():
    return _cancel_event.is_set()


class Command(BaseCommand):
    help = (
        "Analiza incrementalmente chat_history con IA. El CRM se consulta "
        "solo con SELECT y los resultados se guardan en la base default."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="date_from")
        parser.add_argument("--to", dest="date_to")
        parser.add_argument("--lead-id", type=int)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    @staticmethod
    def _process_row(row, *, force, dry_run, existing_keys):
        if _cancel_event.is_set():
            return "cancelled", None
        close_old_connections()
        # Vincula todas las llamadas LLM de este lead a un trace_id único
        # ("lead:{id}") para poder sumar el costo IA por lead desde AIConsumptionLog.
        from intelligence.learning.trace_context import bind_trace_id, release_trace_id
        trace_token = bind_trace_id(f"lead:{row['id']}")
        try:
            raw_history = row["chat_history"]
            history_hash = conversation_hash(raw_history)
            if (row["id"], history_hash) in existing_keys and not force:
                return "skipped", None

            structural = analyze_chat_history(raw_history)
            if not structural["messages"]:
                return "skipped", None

            skill = AnalizarConversacionLeadSkill()
            result = skill.execute({"messages": structural["messages"]})
            if not result.success:
                return "failed", f"Lead {row['id']}: {result.message}"

            assessment = result.data
            if not structural["bidirectional"]:
                assessment["qualified_status"] = "not_confirmed"
                assessment["qualified_evidence"] = []
            if not structural["contacted"]:
                assessment["first_response_status"] = "not_applicable"
                assessment["first_response_evidence"] = []
            if dry_run:
                return "analyzed", None

            with transaction.atomic(using="default"):
                (
                    LeadConversationAssessment.objects.using("default")
                    .update_or_create(
                        source_lead_id=row["id"],
                        history_hash=history_hash,
                        analysis_version=ANALYSIS_VERSION,
                        defaults={
                            "qualified_status": assessment[
                                "qualified_status"
                            ],
                            "visit_intent_status": assessment[
                                "visit_intent_status"
                            ],
                            "qualified_confidence": assessment[
                                "qualified_confidence"
                            ],
                            "visit_intent_confidence": assessment[
                                "visit_intent_confidence"
                            ],
                            "qualified_evidence": assessment[
                                "qualified_evidence"
                            ],
                            "visit_intent_evidence": assessment[
                                "visit_intent_evidence"
                            ],
                            "reason": assessment["reason"],
                            "first_response_status": assessment[
                                "first_response_status"
                            ],
                            "first_response_confidence": assessment[
                                "first_response_confidence"
                            ],
                            "relevance_score": assessment["relevance_score"],
                            "coverage_score": assessment["coverage_score"],
                            "directness_score": assessment[
                                "directness_score"
                            ],
                            "personalization_score": assessment[
                                "personalization_score"
                            ],
                            "lead_request_items": assessment[
                                "lead_request_items"
                            ],
                            "answered_request_items": assessment[
                                "answered_request_items"
                            ],
                            "unanswered_request_items": assessment[
                                "unanswered_request_items"
                            ],
                            "first_response_evidence": assessment[
                                "first_response_evidence"
                            ],
                            "attention_reason": assessment[
                                "attention_reason"
                            ],
                            "model_version": assessment["model_version"],
                        },
                    )
                )
            return "analyzed", None
        except Exception as exc:
            return "failed", f"Lead {row['id']}: {exc}"
        finally:
            close_old_connections()
            release_trace_id(trace_token)

    def handle(self, *args, **options):
        lead_id = options["lead_id"]
        date_from = None
        date_to = None
        if lead_id:
            rows = _lead_result_rows(None, None, lead_id=lead_id)
        else:
            if not options["date_from"] or not options["date_to"]:
                raise CommandError("Indica --from y --to, o utiliza --lead-id.")
            try:
                date_from = date.fromisoformat(options["date_from"])
                date_to = date.fromisoformat(options["date_to"])
            except ValueError as exc:
                raise CommandError("Las fechas deben usar YYYY-MM-DD.") from exc
            rows = _lead_result_rows(date_from, date_to)

        if options["limit"] > 0:
            rows = rows[: options["limit"]]
        workers = options["workers"]
        if workers < 1 or workers > 8:
            raise CommandError("--workers debe estar entre 1 y 8.")
        existing_keys = set()
        if rows and not options["force"]:
            existing_keys = set(
                LeadConversationAssessment.objects.using("default")
                .filter(
                    source_lead_id__in=[row["id"] for row in rows],
                    analysis_version=ANALYSIS_VERSION,
                )
                .values_list("source_lead_id", "history_hash")
            )

        run = None
        if not options["dry_run"]:
            interrupted_at = timezone.now()
            (
                AnalysisRun.objects.using("default")
                .filter(
                    status=AnalysisRun.Status.RUNNING,
                    rules_version=ANALYSIS_VERSION,
                )
                .update(
                    status=AnalysisRun.Status.FAILED,
                    completed_at=interrupted_at,
                    error_summary=(
                        "Ejecución interrumpida antes de registrar su cierre."
                    ),
                )
            )
            run = AnalysisRun.objects.using("default").create(
                run_type=AnalysisRun.RunType.MANUAL,
                status=AnalysisRun.Status.RUNNING,
                started_at=interrupted_at,
                heartbeat_at=interrupted_at,
                leads_total=len(rows),
                date_from=date_from,
                date_to=date_to,
                rules_version=ANALYSIS_VERSION,
                model_version=LLMService.DEEPSEEK_MODEL,
            )
            AnalysisRunStep.objects.using("default").create(
                run=run,
                status="started",
                message=(
                    f"Ejecución iniciada · {len(rows)} leads · "
                    f"workers={workers} · modelo={LLMService.DEEPSEEK_MODEL}"
                ),
            )

        analyzed = skipped = failed = cancelled = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_row = {
                executor.submit(
                    self._process_row,
                    row,
                    force=options["force"],
                    dry_run=options["dry_run"],
                    existing_keys=existing_keys,
                ): row
                for row in rows
            }
            for future in as_completed(future_to_row):
                row = future_to_row[future]
                status, error = future.result()
                if status == "cancelled":
                    cancelled += 1
                elif status == "analyzed":
                    analyzed += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    failed += 1
                    self.stderr.write(error)
                if run is not None:
                    AnalysisRunStep.objects.using("default").create(
                        run=run,
                        lead_id=row["id"],
                        status=status,
                        message=error or "",
                    )
                processed = analyzed + skipped + failed + cancelled
                if run is not None and processed % 5 == 0:
                    (
                        AnalysisRun.objects.using("default")
                        .filter(pk=run.pk)
                        .update(
                            heartbeat_at=timezone.now(),
                            leads_analyzed=analyzed,
                            leads_skipped=skipped,
                            leads_failed=failed,
                        )
                    )

        if run is not None:
            run.leads_analyzed = analyzed
            run.leads_skipped = skipped
            run.leads_failed = failed
            if _cancel_event.is_set():
                run.status = AnalysisRun.Status.FAILED
                run.completed_at = timezone.now()
                run.heartbeat_at = run.completed_at
                run.error_summary = "Cancelada por el usuario desde el dashboard."
            else:
                run.status = AnalysisRun.Status.COMPLETED
                run.completed_at = timezone.now()
                run.heartbeat_at = run.completed_at
                run.error_summary = (
                    f"{failed} conversaciones fallidas; pueden reintentarse."
                    if failed
                    else ""
                )
            run.save(
                using="default",
                update_fields=[
                    "status",
                    "completed_at",
                    "heartbeat_at",
                    "leads_analyzed",
                    "leads_skipped",
                    "leads_failed",
                    "error_summary",
                ],
            )
            AnalysisRunStep.objects.using("default").create(
                run=run,
                status="cancelled" if _cancel_event.is_set() else "completed",
                message=(
                    f"Fin · analizados={analyzed}, omitidos={skipped}, "
                    f"fallidos={failed}, cancelados={cancelled}"
                ),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Analizados: {analyzed}; omitidos: {skipped}; fallidos: {failed}; "
                f"cancelados: {cancelled}."
            )
        )
