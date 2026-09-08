from datetime import timedelta
from django.utils import timezone
from .models import ScrapingWorker


def worker_health():
    latest = ScrapingWorker.objects.order_by('-heartbeat_at').first()
    ready = bool(latest and latest.heartbeat_at >= timezone.now() - timedelta(seconds=75))
    return {'ready': ready, 'message': 'Worker disponible' if ready else 'Sin señal reciente del worker',
            'heartbeat_at': latest.heartbeat_at.isoformat() if latest else None,
            'revision': latest.revision if latest else None}
