"""Sanitize operational events; never store session payloads in logs."""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE = re.compile(r'cookie|authorization|password|passwd|pwd|secret|access_token|refresh_token|api_key|sig$', re.I)


def sanitize(value):
    if isinstance(value, dict):
        return {str(k): ('[redacted]' if SENSITIVE.search(str(k)) else sanitize(v)) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [sanitize(v) for v in value[:100]]
    if isinstance(value, str):
        def url(match):
            parts = urlsplit(match[0])
            query = [(k, '[redacted]' if SENSITIVE.search(k) else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
            return urlunsplit(parts._replace(netloc=parts.hostname or '', query=urlencode(query)))
        text = re.sub(r'https?://[^\s<>"\']+', url, value)
        text = re.sub(r'(?i)(authorization\s*[:=]\s*|bearer\s+)[^\s,;]+', r'\1[redacted]', text)
        text = re.sub(r'(?i)((?:password|passwd|pwd|secret|access_token|refresh_token)\s*[:=]\s*)[^\s,;]+', r'\1[redacted]', text)
        return text[:16000]
    return value if value is None or isinstance(value, (bool, int, float)) else str(value)


def runtime_context():
    import os
    import platform
    import socket
    from importlib.metadata import version, PackageNotFoundError
    info = {'python': platform.python_version(), 'host': socket.gethostname(),
            'revision': os.environ.get('SCRAPING_REVISION', 'development')}
    for name in ('camoufox', 'playwright', 'Django'):
        try:
            info[name] = version(name)
        except PackageNotFoundError:
            info[name] = 'missing'
    return info
