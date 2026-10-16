"""Use a separate cookie and persistent server store only on ACM routes."""
import logging
import time

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date

from .session_backend import SessionStore

logger = logging.getLogger(__name__)
COOKIE_NAME = 'acm_sessionid'


class ACMSessionMiddleware(SessionMiddleware):
    def process_request(self, request):
        request._uses_acm_session = request.path_info.startswith(('/acm/', '/api/acm/'))
        if request._uses_acm_session:
            request.session = SessionStore(request.COOKIES.get(COOKIE_NAME))
        else:
            super().process_request(request)

    def process_response(self, request, response):
        if not getattr(request, '_uses_acm_session', False):
            return super().process_response(request, response)
        session = request.session
        empty = session.is_empty()
        if COOKIE_NAME in request.COOKIES and empty:
            response.delete_cookie(COOKIE_NAME, path='/',
                                   domain=settings.SESSION_COOKIE_DOMAIN,
                                   samesite=settings.SESSION_COOKIE_SAMESITE)
            patch_vary_headers(response, ('Cookie',))
        else:
            if session.accessed:
                patch_vary_headers(response, ('Cookie',))
            if (session.modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty and response.status_code < 500:
                if session.get_expire_at_browser_close():
                    max_age = expires = None
                else:
                    max_age = session.get_expiry_age()
                    expires = http_date(time.time() + max_age)
                try:
                    session.save()
                except UpdateError:
                    # A concurrent logout revoked this session. Do not recreate it
                    # or overwrite the cookie from the newer response.
                    response = JsonResponse({'error': 'La sesión cambió. Inicia sesión nuevamente.'}, status=409) if request.path_info.startswith('/api/') else redirect('/acm/login/')
                    response['Cache-Control'] = 'no-store'
                    patch_vary_headers(response, ('Cookie',))
                    return response
                except OSError:
                    logger.exception('ACM session storage unavailable')
                    return JsonResponse({'error': 'No se pudo guardar la sesión. Inténtalo nuevamente.'}, status=503)
                response.set_cookie(COOKIE_NAME, session.session_key,
                                    max_age=max_age, expires=expires,
                                    path='/', domain=settings.SESSION_COOKIE_DOMAIN,
                                    secure=settings.SESSION_COOKIE_SECURE or None,
                                    httponly=True, samesite=settings.SESSION_COOKIE_SAMESITE)
        return response
