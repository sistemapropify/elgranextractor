"""Local service health; contains counts only, never lead personal data."""
import json
from pathlib import Path
from django.utils import timezone
from django.utils.dateparse import parse_datetime

STATUS_PATH = Path(__file__).resolve().parents[1] / 'var' / 'lead-control-status.json'


def runtime_status():
    try:
        data = json.loads(STATUS_PATH.read_text(encoding='utf-8'))
        heartbeat = parse_datetime(data['heartbeat'])
        data['running'] = bool(heartbeat and timezone.is_aware(heartbeat) and (timezone.now()-heartbeat).total_seconds() < 180)
        data['healthy'] = data['running'] and not data.get('error')
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return {'running': False, 'healthy': False}


def write_status(data):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps({**data, 'heartbeat': timezone.now().isoformat()}, ensure_ascii=False), encoding='utf-8')
    temporary.replace(STATUS_PATH)
