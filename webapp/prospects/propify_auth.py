"""Autenticación Propify aislada de los usuarios y sesiones de Prometeo."""

from dataclasses import dataclass
from functools import wraps
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import MobileProspectUser


WEB_TOKEN_SESSION_KEY = 'prospects_propify_access_token'
WEB_PROFILE_SESSION_KEY = 'prospects_propify_profile'


class PropifyAuthError(Exception):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PropifyPrincipal:
    mobile_user: MobileProspectUser
    profile: dict
    token: str

    @property
    def is_authenticated(self):
        return True

    @property
    def username(self):
        return self.mobile_user.username

    @property
    def pk(self):
        return self.mobile_user.pk


def _json_object(response):
    try:
        payload = response.json()
    except ValueError as exc:
        raise PropifyAuthError('Propify devolvió una respuesta inválida.', 502) from exc
    if not isinstance(payload, dict):
        raise PropifyAuthError('Propify devolvió una respuesta inválida.', 502)
    return payload


def _profile_from_payload(payload):
    profile = payload.get('user', payload)
    if not isinstance(profile, dict):
        raise PropifyAuthError('Propify no devolvió el perfil del usuario.', 502)
    return profile


def _mobile_user_for_profile(profile):
    username = str(
        profile.get('username')
        or profile.get('email')
        or profile.get('phone')
        or ''
    ).strip()
    if not username:
        raise PropifyAuthError('El perfil de Propify no contiene un usuario identificable.', 502)

    propify_user_id = str(profile.get('id') or profile.get('pk') or '').strip()
    user, _ = MobileProspectUser.objects.get_or_create(
        username=username,
        defaults={'propify_user_id': propify_user_id},
    )
    if propify_user_id and user.propify_user_id != propify_user_id:
        user.propify_user_id = propify_user_id
        user.save(update_fields=['propify_user_id'])
    return user


def fetch_propify_profile(token):
    try:
        response = requests.get(
            settings.PROPIFY_AUTH_ME_URL,
            headers={
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise PropifyAuthError('No se pudo conectar con Propify para validar la sesión.', 503) from exc

    if response.status_code in (401, 403):
        raise PropifyAuthError('La sesión de Propify venció o no es válida.', 401)
    if response.status_code != 200:
        raise PropifyAuthError('Propify no pudo validar la sesión.', 502)
    return _profile_from_payload(_json_object(response))


def principal_from_token(token):
    profile = fetch_propify_profile(token)
    return PropifyPrincipal(
        mobile_user=_mobile_user_for_profile(profile),
        profile=profile,
        token=token,
    )


def authenticate_propify_credentials(username, password):
    try:
        response = requests.post(
            settings.PROPIFY_AUTH_TOKEN_URL,
            json={'username': username, 'password': password},
            headers={'Accept': 'application/json'},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise PropifyAuthError('No se pudo conectar con Propify. Inténtalo nuevamente.', 503) from exc

    payload = _json_object(response)
    if response.status_code in (400, 401, 403):
        detail = payload.get('detail') or payload.get('error') or 'Usuario o contraseña incorrectos.'
        raise PropifyAuthError(str(detail), 401)
    if response.status_code not in (200, 201):
        raise PropifyAuthError('Propify no pudo iniciar la sesión.', 502)

    token = str(payload.get('access') or payload.get('token') or '').strip()
    if not token:
        raise PropifyAuthError('Propify no devolvió un token de acceso.', 502)
    return payload, principal_from_token(token)


class PropifyBearerAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != b'bearer':
            raise AuthenticationFailed('Encabezado Authorization inválido.')
        try:
            token = parts[1].decode('utf-8')
            principal = principal_from_token(token)
        except (UnicodeDecodeError, PropifyAuthError) as exc:
            raise AuthenticationFailed(str(exc)) from exc
        return principal, token


def clear_web_propify_session(request):
    request.session.pop(WEB_TOKEN_SESSION_KEY, None)
    request.session.pop(WEB_PROFILE_SESSION_KEY, None)


def get_web_propify_principal(request):
    cached = getattr(request, 'propify_principal', None)
    if cached is not None:
        return cached
    token = str(request.session.get(WEB_TOKEN_SESSION_KEY, '')).strip()
    if not token:
        return None
    try:
        principal = principal_from_token(token)
    except PropifyAuthError:
        clear_web_propify_session(request)
        return None
    request.propify_principal = principal
    return principal


def safe_next_url(request, default='/prospects/'):
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def propify_web_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        principal = get_web_propify_principal(request)
        if principal is None:
            query = urlencode({'next': request.get_full_path()})
            return redirect(f'/prospects/login/?{query}')
        request.propify_user = principal
        return view_func(request, *args, **kwargs)
    return wrapped

