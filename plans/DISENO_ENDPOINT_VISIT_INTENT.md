# Diseño: Endpoint de "Intención de visita" para el CRM

> Objetivo: exponer un endpoint server-to-server (protegido por API key) que el
> CRM use para **visualizar los leads en los que se detectó un intento de
> visita** (confirmado por la evaluación IA/determinista de lead_intelligence).

---

## 1. Dónde se detecta y almacena el intento de visita (verificado en código)

- `LeadConversationAssessment` (BD `default`, tabla `prometeo_lead_conversation_assessment`):
  - `visit_intent_status` (`confirmed`/`not_confirmed`/`ambiguous`)
  - `visit_intent_confidence`, `visit_intent_evidence` (JSON con los mensajes del
    lead que sustentan el intento), `analyzed_at`, `source_lead_id`.
- Determinista: `analyze_chat_history(...)["visit_intent"]` + `visit_intent_at`
  (el lead propone/acepta visitar, ofrece disponibilidad, acuerda fecha/hora).
- IA: `contextual_analysis` refina a `visit_intent_status`.
- El pipeline de evaluación (comando `analyze_lead_conversations`, cron) persiste
  el assessment → fuente fiable para el endpoint.
- Datos del lead en el CRM (`propifai`, solo SELECT): `lead` (contacto, agente,
  estado, `date_entry`), `lead_properties` (vínculo lead→propiedad),
  `property` (código/título).
- `visit_resolution.resolve_visits_for_leads(lead_ids)` → si la visita además
  quedó **registrada** en el CRM (`visit_registered`).

## 2. Endpoint propuesto

- **Ruta:** `GET /analisis-crm/api/visit-intent/`
- **Nombre de vista:** `visit_intent_api` en `lead_intelligence/analytics_api.py`
  (mismo módulo/patrón que `attention_quality_api` / `property_dashboard_api`).
- **Auth:** `@analytics_access_required` (header `X-Analytics-API-Key` == env
  `ANALYTICS_BRIDGE_API_KEY`, o sesión de gerencia) + `@require_GET`.
- **Params:**
  - `from` / `to` (periodo, vía `_parameters`; filtra por `analyzed_at`).
  - `agent` (opcional): id de agente asignado para filtrar.
  - `status` (opcional, default `confirmed`): confirmed | ambiguous.

## 3. Forma de la respuesta (CRAM-friendly)

```json
{
  "generated_at": "2026-08-13T14:00:00-05:00",
  "date_from": "2026-08-01",
  "date_to": "2026-08-13",
  "count": 12,
  "items": [
    {
      "lead_id": 3384,
      "contact_name": "Elia Flores",
      "phone": "+51994607186",
      "channel": "whatsapp",
      "agent_id": 3,
      "agent_name": "Carlos Torres",
      "status_name": "Interesado en vender",
      "entered_at": "2026-08-13T13:43:58-05:00",
      "visit_intent_status": "confirmed",
      "visit_intent_confidence": 0.85,
      "visit_intent_at": "2026-08-13T14:02:11-05:00",
      "visit_intent_evidence": [
        {"message_index": 4, "sender": "lead", "text": "Sí, quisiera visitarlo mañana", "timestamp": "2026-08-13T14:02:11-05:00"}
      ],
      "property_id": 99,
      "property_code": "PROP000099",
      "property_title": "Terreno ideal para proyecto inmobiliario",
      "visit_registered": false
    }
  ]
}
```

## 4. Lógica (función de servicio `get_visit_intent_leads`)

1. `LeadConversationAssessment.objects.using("default")` con
   `visit_intent_status=status`, `analyzed_at` en [from,to] → lista de
   `source_lead_id` + assessment (última versión por lead).
2. SELECT al CRM (`propifai`) de esos leads: contacto (nombre, teléfono), agente
   asignado, estado, `date_entry`, `id_chatwoot`.
3. `lead_properties` → propiedad (código/título) por lead (reutiliza el patrón de
   `property_dashboard._load_lead_rows`).
4. `resolve_visits_for_leads(lead_ids)` → marca `visit_registered` por lead.
5. `visit_intent_at` y `visit_intent_evidence` desde `assessment` (usar
   `_evidence_timestamp`/`_apply_contextual_assessment` para el timestamp).
6. Ordenar por `visit_intent_at` descendente; paginación/limit por query (`limit`).

## 5. Pasos de implementación (orden)

1. Añadir `get_visit_intent_leads(date_from, date_to, status, agent_id, limit)`
   en `lead_intelligence/analytics_api.py` (o `services.py`).
2. Añadir vista `visit_intent_api` (GET, `@analytics_access_required`) en
   `analytics_api.py`.
3. Registrar ruta en `analisis_crm/urls.py`:
   `path('api/visit-intent/', lead_analytics_api.visit_intent_api, name='visit_intent_api')`.
4. Tests (SimpleTestCase, sin BD): resolución de ruta, 403 sin API key, forma del
   payload con mocks (assessment + CRM) — mismo patrón que
   `EvaluacionAutomaticaApiTests`.
5. Verificación con datos reales (leads con `visit_intent_status=confirmed`).
6. Commit + push (deploy).

## 6. Fuera de alcance

- Cambiar cómo se detecta el intento de visita (ya existe).
- Endpoint de UI (es server-to-server para el CRM).
- `LeadMilestone` (no se escribe actualmente para visit intent; se usa
  `analyzed_at`/evidencia como marca temporal).
