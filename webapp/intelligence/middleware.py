"""
Middleware de autenticación para Prometeo.
Establece request.current_user en cada request autenticado.
Redirige a login si no hay sesión activa (excepto en rutas públicas).
"""

import re
from django.shortcuts import redirect
from django.urls import reverse
from .authentication import get_authenticated_user


# Rutas que no requieren autenticación
PUBLIC_PATHS = [
    r'^/$',                      # Página principal (landing page pública)
    r'^/login/?$',
    r'^/register/?$',
    r'^/api/',
    r'^/admin/',
    r'^/static/',
]


class AuthenticationMiddleware:
    """
    Middleware que:
    1. Establece request.current_user si hay sesión activa
    2. Redirige a login si no hay sesión (excepto rutas públicas)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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

    def _is_public_path(self, path: str) -> bool:
        """Verifica si una ruta es pública (no requiere autenticación)."""
        for pattern in PUBLIC_PATHS:
            if re.match(pattern, path):
                return True
        return False
