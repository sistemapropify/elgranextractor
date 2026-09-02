"""Persistencia y notificaciones de intenciones de visita del CRM."""

import json
import logging
import os
from datetime import date, datetime, time, timedelta

import requests
from django.conf import settings
from django.db import connections
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from lead_intelligence.analytics_api import get_visit_intent_leads
from lead_intelligence.conversation_analysis import analyze_chat_history

from .models import CrmVisitIntentAlert, MobileNotificationDevice


logger = logging.getLogger(__name__)


def crm_alerts_start_at():
    """Inicio operativo de alertas; los datos anteriores quedan fuera del módulo."""
    configured = str(getattr(settings, "CRM_ALERTS_START_DATE", "2026-08-24")).strip()
    start_date = parse_date(configured)
    if start_date is None:
        logger.error("CRM_ALERTS_START_DATE inválida: %s; se usará 2026-08-24", configured)
        start_date = date(2026, 8, 24)
    return timezone.make_aware(
        datetime.combine(start_date, time.min),
        timezone.get_current_timezone(),
    )


def _aware(value):
    if value is None:
        return None
    parsed = parse_datetime(str(value)) if not hasattr(value, "tzinfo") else value
    if parsed is not None and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _firebase_access_token():
    """Devuelve credenciales HTTP v1 solo cuando Firebase está configurado."""
    raw_credentials = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw_credentials:
        return None, None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        info = json.loads(raw_credentials)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        credentials.refresh(Request())
        return info.get("project_id"), credentials.token
    except Exception:
        logger.exception("No se pudieron crear las credenciales de Firebase")
        return None, None


def send_new_alert_push(alert):
    """Envía un aviso genérico, sin datos personales, a supervisores."""
    project_id, access_token = _firebase_access_token()
    if not project_id or not access_token:
        return 0

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    sent = 0
    devices = MobileNotificationDevice.objects.filter(
        active=True,
        user__can_view_crm_alerts=True,
    )
    for device in devices.iterator():
        payload = {
            "message": {
                device.target_type: device.registration_id,
                "notification": {
                    "title": "Nueva intención de visita",
                    "body": "Ingresa a Propitools para revisar y atender la alerta.",
                },
                "data": {
                    "type": "crm_visit_intent",
                    "alert_id": str(alert.pk),
                },
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": "crm_visit_intent",
                        "sound": "default",
                    },
                },
            }
        }
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=15,
            )
            if response.ok:
                sent += 1
            elif response.status_code in (400, 404) and "UNREGISTERED" in response.text:
                device.active = False
                device.save(update_fields=["active", "updated_at"])
            else:
                logger.warning("FCM rechazó el dispositivo %s: HTTP %s", device.pk, response.status_code)
        except requests.RequestException:
            logger.exception("No se pudo enviar la alerta CRM por FCM")
    return sent


def sync_crm_visit_alerts(date_from=None, date_to=None, limit=500):
    """Sincroniza nuevas intenciones y detecta la primera respuesta del agente."""
    date_to = date_to or timezone.localdate()
    start_at = crm_alerts_start_at()
    date_from = max(date_from or (date_to - timedelta(days=45)), start_at.date())
    items = get_visit_intent_leads(date_from, date_to, limit=limit)
    created_alerts = []
    for item in items:
        detected_at = _aware(item.get("visit_intent_at")) or timezone.now()
        if detected_at < start_at:
            continue
        alert, created = CrmVisitIntentAlert.objects.update_or_create(
            source_lead_id=item["lead_id"],
            detected_at=detected_at,
            defaults={
                "agent_id": item.get("agent_id"),
                "agent_name": item.get("agent_name") or "",
                "contact_name": item.get("contact_name") or "",
                "phone": item.get("phone") or "",
                "property_id": item.get("property_id"),
                "property_code": item.get("property_code") or "",
                "property_title": item.get("property_title") or "",
                "evidence": item.get("visit_intent_evidence") or [],
            },
        )
        if created:
            created_alerts.append(alert)

    pending = list(CrmVisitIntentAlert.objects.filter(
        status=CrmVisitIntentAlert.Status.PENDING,
        detected_at__gte=start_at,
    ))
    if pending:
        lead_ids = sorted({item.source_lead_id for item in pending})
        placeholders = ",".join(["%s"] * len(lead_ids))
        with connections["propifai"].cursor() as cursor:
            cursor.execute(
                f"SELECT id, chat_history FROM dbo.lead WHERE id IN ({placeholders})",
                lead_ids,
            )
            histories = {int(row[0]): row[1] for row in cursor.fetchall()}
        for alert in pending:
            messages = analyze_chat_history(histories.get(alert.source_lead_id))["messages"]
            response_at = next(
                (
                    parsed
                    for message in messages
                    if message.get("sender") == "agent"
                    and (parsed := _aware(message.get("timestamp"))) is not None
                    and parsed > alert.detected_at
                ),
                None,
            )
            if response_at:
                alert.responded_at = response_at
                alert.status = CrmVisitIntentAlert.Status.FOLLOW_UP
                alert.save(update_fields=["responded_at", "status", "updated_at"])

    for alert in created_alerts:
        send_new_alert_push(alert)
    return {"created": len(created_alerts), "checked": len(items)}


def get_crm_lead_conversation(lead_id):
    """Devuelve la conversación normalizada completa de un lead del CRM."""
    with connections["propifai"].cursor() as cursor:
        cursor.execute("SELECT chat_history FROM dbo.lead WHERE id = %s", [lead_id])
        row = cursor.fetchone()
    if row is None:
        return []
    messages = analyze_chat_history(row[0])["messages"]
    return [
        {
            "sender": message["sender"],
            "text": message["text"],
            "timestamp": message["timestamp"].isoformat(),
        }
        for message in messages
    ]
