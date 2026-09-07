"""Server-configured n8n gateway. Credentials and URLs never come from campaigns."""
import os
from datetime import timedelta
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db import connections


def config(name):
    return getattr(settings, name, None) or os.environ.get(name, '')


def gateway_ready():
    url = config('REMARKETING_GATEWAY_URL')
    return bool(url and urlsplit(url).scheme == 'https' and config('REMARKETING_GATEWAY_TOKEN'))


class RemarketingGateway:
    def __init__(self):
        if not gateway_ready():
            raise ValueError('Configura REMARKETING_GATEWAY_URL (HTTPS) y REMARKETING_GATEWAY_TOKEN.')
        self.url = config('REMARKETING_GATEWAY_URL').rstrip('/')

    def post(self, action, payload):
        response = requests.post(f'{self.url}/{action}', json=payload, headers={'Authorization': f"Bearer {config('REMARKETING_GATEWAY_TOKEN')}"}, timeout=(5, 25), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError('El gateway no confirmó la operación.')
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError('Respuesta inválida del gateway.')
        return result

    def snapshot(self, lead_id):
        try:
            return self.post('snapshot', {'lead_id': lead_id})
        except requests.RequestException as exc:
            raise ValueError('Fuente de conversación no disponible.') from exc

    def send(self, delivery, snapshot):
        enrollment = delivery.enrollment
        return self.post('send', {
            'idempotency_key': str(delivery.idempotency_key),
            'lead_id': enrollment.source_lead_id,
            'contact_key': enrollment.contact_key,
            'message': delivery.body,
            'expected_last_inbound_at': enrollment.last_inbound_at.isoformat(),
            'snapshot_version': snapshot.get('version'),
            'not_after': (enrollment.last_inbound_at + timedelta(hours=24, minutes=-enrollment.policy['window_margin_minutes'])).isoformat(),
        })


def crm_snapshot(lead_id):
    """Read-only CRM snapshot used for previews/enrollment, not final send authorization."""
    with connections['propifai'].cursor() as cursor:
        cursor.execute('''
            SELECT l.id AS lead_id, l.chat_history AS messages,
                COALESCE(l.date_entry, l.created_at) AS entered_at,
                l.assigned_to_id AS agent_id, l.id_chatwoot,
                c.phone, COALESCE(ls.name, '') AS status_name,
                COALESCE(cl.name, '') AS channel_name,
                COALESCE(c.first_name, '') AS nombre,
                COALESCE(u.first_name, '') AS agente,
                COALESCE((SELECT TOP 1 p.title FROM dbo.lead_properties lp
                    JOIN dbo.property p ON p.id = lp.property_id
                    WHERE lp.lead_id = l.id ORDER BY p.id), '') AS propiedad
            FROM dbo.lead l
            LEFT JOIN dbo.contact c ON c.id = l.contact_id
            LEFT JOIN dbo.[user] u ON u.id = l.assigned_to_id
            LEFT JOIN dbo.lead_status ls ON ls.id = l.lead_status_id
            LEFT JOIN dbo.canal_lead cl ON cl.id = l.canal_lead_id
            WHERE l.id = %s
        ''', [lead_id])
        row = cursor.fetchone()
        if not row:
            raise ValueError('Lead no encontrado.')
        snapshot = dict(zip([col[0] for col in cursor.description], row))
    phone = ''.join(c for c in str(snapshot.pop('phone') or '') if c.isdigit())
    conversation = snapshot.pop('id_chatwoot')
    snapshot['contact_key'] = f'phone:{phone}' if phone else (f'chatwoot:{conversation}' if conversation else '')
    return snapshot


def discover_lead_ids(after_id, limit=200):
    with connections['propifai'].cursor() as cursor:
        cursor.execute('SELECT TOP (%s) id FROM dbo.lead WHERE id > %s AND chat_history IS NOT NULL ORDER BY id', [limit, after_id])
        return [row[0] for row in cursor.fetchall()]
