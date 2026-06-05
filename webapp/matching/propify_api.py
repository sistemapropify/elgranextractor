"""
Cliente API para consumir los endpoints de Propify (api.propify.pe).
Maneja autenticaci�n JWT, refresh de tokens y paginaci�n.
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)

PROPIFY_API_BASE = "https://api.propify.pe"
PROPIFY_AUTH_ENDPOINT = "/api/auth/token/"

# Credenciales (idealmente en .env)
PROPIFY_USERNAME = "adminpropify"
PROPIFY_PASSWORD = "yosoytupapi"


class PropifyApiClient:
    """
    Cliente para la API de Propify.
    Mantiene el token de acceso y lo refresca autom�ticamente cuando expira.
    """

    def __init__(self):
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None

    def _authenticate(self) -> bool:
        """Obtiene un nuevo token de acceso usando username/password."""
        try:
            resp = requests.post(
                f"{PROPIFY_API_BASE}{PROPIFY_AUTH_ENDPOINT}",
                json={
                    "username": PROPIFY_USERNAME,
                    "password": PROPIFY_PASSWORD,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access")
                self._refresh_token = data.get("refresh")
                return True
            else:
                logger.error(f"Error al autenticar en Propify API: {resp.status_code} {resp.text[:200]}")
                return False
        except requests.RequestException as e:
            logger.error(f"Error de conexi�n al autenticar en Propify API: {e}")
            return False

    def _refresh_access_token(self) -> bool:
        """Refresca el token de acceso usando el refresh token."""
        if not self._refresh_token:
            return self._authenticate()
        try:
            resp = requests.post(
                f"{PROPIFY_API_BASE}/api/token/refresh/",
                json={"refresh": self._refresh_token},
                timeout=30,
            )
            if resp.status_code == 200:
                self._access_token = resp.json().get("access")
                return True
            else:
                # Si falla el refresh, re-autenticar
                return self._authenticate()
        except requests.RequestException:
            return self._authenticate()

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers con Authorization Bearer."""
        if not self._access_token:
            self._authenticate()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Realiza una petici�n HTTP a la API de Propify.
        Intenta refresh autom�tico si el token expir�.
        """
        url = f"{PROPIFY_API_BASE}{path}"
        headers = self._get_headers()

        for attempt in range(2):  # M�ximo 2 intentos (1 normal + 1 con refresh)
            try:
                resp = requests.request(
                    method, url, headers=headers, timeout=30, **kwargs
                )
                if resp.status_code == 401:
                    # Token expirado, refrescar y reintentar
                    if self._refresh_access_token():
                        headers = self._get_headers()
                        continue
                    else:
                        logger.error("No se pudo renovar el token de Propify API")
                        return None
                if resp.status_code == 200:
                    return resp.json()
                else:
                    logger.warning(
                        f"Error en Propify API {method} {path}: {resp.status_code}"
                    )
                    return None
            except requests.RequestException as e:
                logger.error(f"Error de conexi�n en Propify API: {e}")
                return None
        return None

    def get_matches(
        self, page: int = 1, page_size: int = 50, **filters
    ) -> Optional[Dict[str, Any]]:
        """
        GET /api/crm/matches/
        Retorna lista paginada de matches.
        """
        params = {"page": page, "page_size": page_size}
        params.update(filters)
        return self._request("GET", "/api/crm/matches/", params=params)

    def get_requirements(
        self, page: int = 1, page_size: int = 50, **filters
    ) -> Optional[Dict[str, Any]]:
        """
        GET /api/crm/requirements/
        Retorna lista paginada de requirements.
        """
        params = {"page": page, "page_size": page_size}
        params.update(filters)
        return self._request("GET", "/api/crm/requirements/", params=params)

    def get_requirement_detail(self, requirement_id: int) -> Optional[Dict[str, Any]]:
        """GET /api/crm/requirements/{id}/"""
        return self._request("GET", f"/api/crm/requirements/{requirement_id}/")

    def get_matches_by_property(self, property_id: int) -> Optional[Dict[str, Any]]:
        """GET /api/crm/matches/received-matches/?property={id}"""
        return self._request(
            "GET", "/api/crm/matches/received-matches/", params={"property": property_id}
        )

    def get_matches_by_requirement(self, requirement_id: int) -> Optional[Dict[str, Any]]:
        """GET /api/crm/matches/received-matches/?requirement={id}"""
        return self._request(
            "GET",
            "/api/crm/matches/received-matches/",
            params={"requirement": requirement_id},
        )


# Instancia singleton para reutilizar
_client: Optional[PropifyApiClient] = None


def get_propify_client() -> PropifyApiClient:
    """Retorna la instancia singleton del cliente Propify API."""
    global _client
    if _client is None:
        _client = PropifyApiClient()
    return _client
