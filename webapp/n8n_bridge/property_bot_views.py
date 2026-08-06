"""API externa y dashboard del respondedor inicial de WhatsApp."""

import hmac
import os
from datetime import time

from django.contrib import messages
from django.db.models import Avg, Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from intelligence.permissions import has_permission
from n8n_bridge.models import (
    PropertyBotConfiguration,
    PropertyBotControlAudit,
    PropertyBotInitialResponse,
)
from n8n_bridge.services.initial_property_config import get_bot_configuration, schedule_state
from n8n_bridge.services.initial_property_responder import process_initial_message


def _api_key_valid(request):
    expected = os.environ.get("N8N_BRIDGE_API_KEY", "")
    received = request.headers.get("X-N8N-API-Key", "")
    return bool(expected) and hmac.compare_digest(received, expected)


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def initial_property_response(request):
    if not _api_key_valid(request):
        return Response({"success": False, "error": "API key inválida"}, status=status.HTTP_401_UNAUTHORIZED)

    payload = dict(request.data)
    payload["message_id"] = payload.get("message_id") or request.headers.get("X-Idempotency-Key", "")
    missing = [field for field in ("message_id", "phone", "text") if not str(payload.get(field) or "").strip()]
    if missing:
        return Response(
            {"success": False, "error": f"Campos requeridos: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(str(payload["text"])) > 2000:
        return Response({"success": False, "error": "text excede 2000 caracteres"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = process_initial_message(payload)
    except Exception as exc:
        return Response(
            {
                "success": False,
                "action": "ignore",
                "reply_text": "",
                "reason_code": "INTERNAL_ERROR",
                "error": type(exc).__name__,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(result, status=status.HTTP_200_OK)


def _request_user(request):
    return getattr(request, "current_user", None)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


@has_permission(required_levels=[4, 5])
@require_http_methods(["GET", "POST"])
def property_bot_dashboard(request):
    config = get_bot_configuration()
    if request.method == "POST":
        before = {
            "enabled": config.enabled,
            "start": config.start_time.strftime("%H:%M"),
            "end": config.end_time.strftime("%H:%M"),
        }
        try:
            start_hour, start_minute = request.POST.get("start_time", "00:00").split(":")
            end_hour, end_minute = request.POST.get("end_time", "05:00").split(":")
            config.enabled = request.POST.get("enabled") == "on"
            config.start_time = time(int(start_hour), int(start_minute))
            config.end_time = time(int(end_hour), int(end_minute))
            config.updated_by = _request_user(request)
            config.save()
        except (ValueError, TypeError):
            messages.error(request, "Horario inválido.")
            return redirect("property-bot-dashboard:dashboard")
        after = {
            "enabled": config.enabled,
            "start": config.start_time.strftime("%H:%M"),
            "end": config.end_time.strftime("%H:%M"),
        }
        PropertyBotControlAudit.objects.create(
            action="configuration_update",
            previous_value=before,
            new_value=after,
            actor=_request_user(request),
            ip_address=_client_ip(request),
        )
        messages.success(request, "Configuración del bot actualizada.")
        return redirect("property-bot-dashboard:dashboard")

    rows = PropertyBotInitialResponse.objects.all()
    totals = rows.aggregate(total=Count("id"), avg_latency=Avg("latency_ms"))
    total = totals["total"] or 0

    def _pct(value):
        return round((value / total) * 100) if total else 0

    responded_ok = rows.filter(
        action="respond_once", review_status="confirmed_ok"
    ).count()
    responded_error = rows.filter(
        action="respond_once", review_status="confirmed_error"
    ).count()
    ignored_ok = rows.filter(action="ignore", review_status="confirmed_ok").count()
    ignored_error = rows.filter(
        action="ignore", review_status="confirmed_error"
    ).count()
    responded = rows.filter(action="respond_once").count()
    ignored = rows.filter(action="ignore").count()
    review = rows.filter(review_status="pending").count()
    errors = rows.filter(
        reason_code__in=["INTERNAL_ERROR", "VALIDATION_FAILED"]
    ).count()

    metrics = {
        "total": total,
        "responded": responded,
        "ignored": ignored,
        "review": review,
        "errors": errors,
        "avg_latency": round(totals["avg_latency"] or 0),
        # Desglose por revisión humana dentro de cada acción
        "responded_ok": responded_ok,
        "responded_error": responded_error,
        "ignored_ok": ignored_ok,
        "ignored_error": ignored_error,
        # Porcentajes sobre el total
        "responded_pct": _pct(responded),
        "ignored_pct": _pct(ignored),
        "review_pct": _pct(review),
        "errors_pct": _pct(errors),
    }
    state = schedule_state(config)

    # Interacciones agrupadas POR LEAD (conversación), no por evento.
    # Por cada conversación se muestra su decisión: si hubo respond_once se usa
    # ese evento (propiedad, tipo, latencia y revisión); si no, el más reciente.
    events = list(rows.order_by("-received_at")[:500])

    # Rellenar teléfono/nombre faltantes (filas previas al nuevo esquema):
    # 1) desde la memoria episódica (episode_id → lead), 2) compartir entre
    # eventos del mismo hilo.
    from intelligence.models import EpisodicMemory

    episode_ids = [e.episode_id for e in events if e.episode_id and not e.phone]
    if episode_ids:
        episodes = {
            ep.id: ep
            for ep in EpisodicMemory.objects.filter(id__in=episode_ids).select_related("user")
        }
        for ev in events:
            if not ev.phone and ev.episode_id in episodes:
                user = episodes[ev.episode_id].user
                if user:
                    ev.phone = user.phone or ""
                    ev.contact_name = user.first_name or ""

    thread_map = {}
    for ev in events:
        thread_map.setdefault(ev.external_conversation_id, []).append(ev)
    for group in thread_map.values():
        known = next((g for g in group if g.phone), None)
        if known:
            for ev in group:
                if not ev.phone:
                    ev.phone = known.phone
                if not ev.contact_name:
                    ev.contact_name = known.contact_name

    leads = {}
    for ev in events:
        key = ev.external_conversation_id or f"msg:{ev.message_id}"
        cur = leads.get(key)
        if cur is None:
            leads[key] = ev
        elif ev.action == "respond_once" and cur.action != "respond_once":
            leads[key] = ev
    interactions = sorted(
        leads.values(), key=lambda e: e.received_at, reverse=True
    )[:100]

    return render(
        request,
        "n8n_bridge/initial_responder/dashboard.html",
        {
            "config": config,
            "schedule": state,
            "metrics": metrics,
            "interactions": interactions,
        },
    )


@has_permission(required_levels=[4, 5])
def property_bot_interaction_detail(request, interaction_id):
    interaction = get_object_or_404(PropertyBotInitialResponse, id=interaction_id)
    return render(request, "n8n_bridge/initial_responder/detail.html", {"interaction": interaction})


@has_permission(required_levels=[4, 5])
@require_POST
def property_bot_review(request, interaction_id):
    interaction = get_object_or_404(PropertyBotInitialResponse, id=interaction_id)
    verdict = request.POST.get("verdict")
    if verdict not in {"confirmed_ok", "confirmed_error"}:
        raise Http404
    interaction.review_status = verdict
    interaction.review_note = request.POST.get("note", "")[:2000]
    interaction.reviewed_at = timezone.now()
    interaction.reviewed_by = _request_user(request)
    interaction.save(update_fields=["review_status", "review_note", "reviewed_at", "reviewed_by"])
    messages.success(request, "Revisión guardada.")
    return redirect("property-bot-dashboard:dashboard")


@has_permission(required_levels=[4, 5])
@require_http_methods(["GET"])
def property_bot_emulator(request):
    """Entorno de pruebas: emulador de WhatsApp conectado al bot real."""
    return render(
        request,
        "n8n_bridge/initial_responder/emulator.html",
        {},
    )


@has_permission(required_levels=[4, 5])
@require_http_methods(["POST"])
def property_bot_emulator_reply(request):
    """Responde en el emulador usando la MISMA lógica real del endpoint de n8n
    (`process_initial_message`): idempotencia, one-shot, guardias, persistencia
    en `PropertyBotInitialResponse` y memoria episódica.

    El emulador NO tiene reglas propias: recibe `phone` y `name` y delega el
    100% de la decisión a la lógica de producción (sin ningún flag adicional).
    """
    import json
    from uuid import uuid4

    from n8n_bridge.services.initial_property_responder import (
        process_initial_message,
    )

    # Modo "payload crudo": el emulador puede enviar el JSON exacto del endpoint.
    raw_payload = str(request.POST.get("payload_json") or "").strip()
    if raw_payload:
        try:
            payload = json.loads(raw_payload)
        except (ValueError, TypeError):
            return JsonResponse(
                {
                    "success": False,
                    "action": "ignore",
                    "reply_text": "",
                    "reason_code": "INVALID_JSON",
                    "note": "El JSON del payload no es válido.",
                }
            )
        if not isinstance(payload, dict):
            return JsonResponse(
                {
                    "success": False,
                    "action": "ignore",
                    "reply_text": "",
                    "reason_code": "INVALID_JSON",
                    "note": "El payload debe ser un objeto JSON.",
                }
            )
        if not str(payload.get("text") or "").strip():
            return JsonResponse(
                {
                    "success": False,
                    "action": "ignore",
                    "reply_text": "",
                    "reason_code": "EMPTY_MESSAGE",
                    "note": "El payload debe incluir el campo 'text'.",
                }
            )
        payload.setdefault("message_id", f"emu-{uuid4().hex}")
        payload.setdefault("human_takeover", False)
        if not str(payload.get("external_conversation_id") or "").strip():
            digits = "".join(
                ch for ch in str(payload.get("phone") or "") if ch.isdigit()
            )
            payload["external_conversation_id"] = f"emulador:{digits}"
        return JsonResponse(process_initial_message(payload))

    text = str(request.POST.get("message") or "").strip()
    name = str(request.POST.get("name") or "").strip()
    phone_raw = str(request.POST.get("phone") or "").strip()
    human_takeover = str(
        request.POST.get("human_takeover") or ""
    ).strip().lower() in {"1", "true", "on", "yes", "si"}

    if not text:
        return JsonResponse(
            {
                "success": False,
                "action": "ignore",
                "reply_text": "",
                "reason_code": "EMPTY_MESSAGE",
                "note": "Escribe un mensaje para probar al bot.",
            }
        )
    if not name:
        return JsonResponse(
            {
                "success": False,
                "action": "ignore",
                "reply_text": "",
                "reason_code": "MISSING_NAME",
                "note": "Ingresa el nombre del contacto (ej. Juan Pérez).",
            }
        )

    phone_digits = "".join(ch for ch in phone_raw if ch.isdigit())
    # Normalizar a E.164 Perú: móvil local de 9 dígitos que empieza en 9 → +51
    if len(phone_digits) == 9 and phone_digits.startswith("9"):
        phone_digits = "51" + phone_digits
    if len(phone_digits) < 8:
        return JsonResponse(
            {
                "success": False,
                "action": "ignore",
                "reply_text": "",
                "reason_code": "INVALID_PHONE",
                "note": "Ingresa un número válido (ej. +51 987 654 321).",
            }
        )

    # Thread estable por teléfono → la guardia one-shot de la lógica real
    # devuelve ALREADY_RESPONDED (silencio) para los mensajes siguientes.
    payload = {
        "message_id": f"emu-{uuid4().hex}",
        "text": text,
        "phone": phone_digits,
        "external_conversation_id": f"emulador:{phone_digits}",
        "contact_name": name,
        "human_takeover": human_takeover,
    }
    return JsonResponse(
        process_initial_message(payload)
    )
