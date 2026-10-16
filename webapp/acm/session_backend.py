"""Server-side ACM sessions, independent of Prometeo's SQL session table."""
import os
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.backends.file import SessionStore as FileSessionStore


class SessionStore(FileSessionStore):
    @classmethod
    def _get_storage_path(cls):
        configured = getattr(settings, 'ACM_SESSION_FILE_PATH', '')
        if configured:
            directory = Path(configured)
        elif os.environ.get('WEBSITE_SITE_NAME'):
            # App Service persistent home is shared by the application's workers.
            directory = Path('/home/data/acm-sessions')
        else:
            root = Path(getattr(settings, 'BASE_DIR', Path(__file__).resolve().parents[1]))
            directory = root.parent / 'outputs' / 'acm-sessions'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        return str(directory)

    def __init__(self, session_key=None):
        super().__init__(session_key)
        self.file_prefix = 'acm_sessionid'
