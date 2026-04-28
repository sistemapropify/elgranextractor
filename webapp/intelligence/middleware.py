"""
Middleware de autenticación para Prometeo.
Establece request.current_user en cada request autenticado.
Redirige a login si no hay sesión activa (excepto en rutas públicas).
Limpia sesiones con IDs inválidos (ej: enteros pre-UUID) para evitar
que Django auth falle al resolver request.user.
"""

import re
import uuid
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import SESSION_KEY
from .authentication import get_authenticated_user


# Rutas que no requieren autenticación
PUBLIC_PATHS = [
    r'^/$',                      # Página principal (landing page pública)
    r'^/login/?$',
    r'^/register/?$',
    r'^/api/',
    r'^/admin/',
    r'^/static/',
    r'^/acm/',                   # ACM - Análisis Comparativo de Mercado (público)
    r'^/ingestas/propiedades/',  # Catálogo público de propiedades
    r'^/market-analysis/',       # Market analysis (heatmap, dashboard) público
]


class AuthenticationMiddleware:
    """
    Middleware que:
    1. Limpia sesiones con IDs inválidos (pre-UUID) para evitar errores
    2. Establece request.current_user si hay sesión activa
    3. Redirige a login si no hay sesión (excepto rutas públicas)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 0. Limpiar _auth_user_id de Django si no es un UUID válido
        #    Esto evita que django.contrib.auth.middleware falle al
        #    resolver request.user con IDs enteros de sesiones pre-UUID.
        self._cleanup_invalid_session(request)

        # 1. Establecer current_user desde la sesión
        request.current_user = get_authenticated_user(request)

        # 2. Verificar autenticación para rutas protegidas
        path = request.path_info

        if not request.current_user and not self._is_public_path(path):
            login_url = reverse('login')
            if path != login_url:
                return redirect(f'{login_url}?next={path}')

        response = self.get_response(request)
        return response

    def _cleanup_invalid_session(self, request):
        """
        Si la sesión tiene _auth_user_id (de Django auth) que no es un
        UUID válido, lo elimina para evitar ValidationError al resolver
        request.user en templates.
        """
        auth_user_id = request.session.get(SESSION_KEY)
        if auth_user_id:
            try:
                uuid.UUID(str(auth_user_id))
            except (ValueError, AttributeError):
                # ID inválido → limpiar toda la sesión
                request.session.flush()

    def _is_public_path(self, path: str) -> bool:
        """Verifica si una ruta es pública (no requiere autenticación)."""
        for pattern in PUBLIC_PATHS:
            if re.match(pattern, path):
                return True
        return False
