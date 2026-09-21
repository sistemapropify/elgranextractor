"""Bounded recovery for transport failures, distinct from invalid property data."""
import asyncio


def portal_blocked(exc):
    text = str(exc).lower()
    return any(marker in text for marker in (
        'detail.blocked', 'navigation.blocked', 'http 403', 'http 429',
        'security verification', 'verify you are human', 'access denied',
    ))


def transient_failure(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        text = str(exc).lower()
        if isinstance(exc, (TimeoutError, ConnectionError)) or any(marker in text for marker in (
            'net::err_', 'ns_error_', 'connection reset', 'connection refused',
            'connection closed', 'timed out', 'timeout', 'name_not_resolved',
            'http 408', 'http 429', 'http 500', 'http 502', 'http 503', 'http 504',
            'navigation.not_ready',
        )):
            return True
        exc = exc.__cause__
    return False


def retry_delay(exc, attempt):
    """Six transport attempts; three attempts for extraction/validation errors."""
    if any(marker in str(exc).lower() for marker in (
            'detail.blocked', 'navigation.blocked', 'http 403', 'http 429')):
        return min(60 * attempt, 120) if attempt < 3 else None
    transient = transient_failure(exc)
    if attempt >= (6 if transient else 3):
        return None
    return min(5 * 2 ** (attempt - 1), 60) if transient else attempt * 5


async def wait_for_retry(delay, emit, **context):
    # Short waits keep cancellation responsive and explain an apparently idle worker.
    remaining = delay
    while remaining > 0:
        await emit(event='recovery.waiting', level='warning', seconds_remaining=remaining,
                   message=f'Reintentando la misma página en {remaining} s; pendiente conservado',
                   **context)
        step = min(remaining, 5)
        await asyncio.sleep(step)
        remaining -= step
