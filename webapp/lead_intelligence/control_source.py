from datetime import timezone as dt_timezone
from django.db import connections
from django.utils import timezone
from .remarketing_gateway import crm_snapshot
from .models import LeadConversationAssessment, LeadEventResolution


def source_versions():
    """Read the whole portfolio cheaply, including edits to old conversations.

    Do not rely on updated_at: external chat ingestion may not update it.
    Only fingerprints leave SQL here; full histories are read for changed leads.
    """
    import hashlib
    import json
    from django.db.models import Max
    from .conversation_identity import ANALYSIS_VERSION
    with connections['propifai'].cursor() as cursor:
        cursor.execute("""
            SELECT l.id, ls.name, l.assigned_to_id,
                COALESCE(l.date_entry, l.created_at),
                HASHBYTES('SHA2_256', COALESCE(l.chat_history, N'')),
                COALESCE(c.first_name, ''), COALESCE(u.first_name, '')
            FROM dbo.lead l
            LEFT JOIN dbo.lead_status ls ON ls.id = l.lead_status_id
            LEFT JOIN dbo.contact c ON c.id = l.contact_id
            LEFT JOIN dbo.[user] u ON u.id = l.assigned_to_id
            ORDER BY l.id DESC
        """)
        rows = cursor.fetchall()
    assessments = dict(LeadConversationAssessment.objects.filter(analysis_version=ANALYSIS_VERSION).order_by().values('source_lead_id').annotate(latest=Max('analyzed_at')).values_list('source_lead_id', 'latest'))
    visits = dict(LeadEventResolution.objects.order_by().values('source_lead_id').annotate(latest=Max('resolved_at')).values_list('source_lead_id', 'latest'))
    result = []
    for row in rows:
        lead_id = row[0]
        raw = list(row[1:]) + [assessments.get(lead_id), visits.get(lead_id)]
        version = hashlib.sha256(json.dumps(raw, default=str, ensure_ascii=False).encode()).hexdigest()
        result.append((lead_id, version, row[1] or ''))
    return result


def source_snapshot(lead_id):
    snapshot = crm_snapshot(lead_id)
    snapshot['observed_at'] = timezone.now().isoformat()
    if snapshot.get('entered_at'):
        value = snapshot['entered_at']
        if timezone.is_naive(value):
            value = value.replace(tzinfo=dt_timezone.utc)
        snapshot['entered_at'] = value.isoformat()
    # Reuse existing evaluated intent with matching history; never call the LLM.
    try:
        from .conversation_identity import ANALYSIS_VERSION, conversation_hash
        assessment = LeadConversationAssessment.objects.filter(source_lead_id=lead_id, analysis_version=ANALYSIS_VERSION, history_hash=conversation_hash(snapshot['messages']), visit_intent_status='confirmed').order_by('-analyzed_at').first()
        if assessment:
            evidence = [entry for entry in assessment.visit_intent_evidence if entry.get('timestamp')]
            if evidence:
                snapshot['visit_intent_at'] = min(entry['timestamp'] for entry in evidence)
                snapshot['visit_evidence'] = {'source': 'assessed_conversation', 'items': evidence}
    except Exception:
        snapshot['intent_analysis'] = 'unavailable'
    if snapshot.get('visit_intent_at'):
        from .visit_resolution import VISIT_RESOLUTION_VERSION
        resolution = LeadEventResolution.objects.filter(source_lead_id=lead_id, resolver_version=VISIT_RESOLUTION_VERSION, resolution_status='confirmed', event_created_at__gte=snapshot['visit_intent_at']).order_by('event_created_at').first()
        if resolution and resolution.event_created_at:
            snapshot['visit_registered_at'] = resolution.event_created_at.isoformat()
    return snapshot


def source_page(after_id, limit):
    with connections['propifai'].cursor() as cursor:
        cursor.execute('SELECT TOP (%s) id FROM dbo.lead WHERE id > %s ORDER BY id', [limit, after_id])
        return [row[0] for row in cursor.fetchall()]
