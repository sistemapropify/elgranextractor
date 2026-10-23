"""Administrative bridge from archived COFOPRI manifests to Catastro Maestro D1."""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from . import geollaqta_bulk, registry_cloud
from .master_d1 import Gateway
from .storage import R2, StorageError
from .views import admin_required


def _private(value, status=200):
    response = JsonResponse(value, status=status,
                            json_dumps_params={'ensure_ascii': False})
    response['Cache-Control'] = 'private, no-store'
    response['Vary'] = 'Cookie'
    return response


def _ubigeo(request):
    value = str(request.GET.get('ubigeo') or
                (json.loads(request.body or b'{}').get('ubigeo')
                 if request.method == 'POST' else '040126'))
    registry_cloud.validate_district(value)
    return value


@require_GET
@admin_required
def status(request):
    try:
        ubigeo = _ubigeo(request)
        return _private(geollaqta_bulk.migration_status(
            Gateway(), ubigeo, R2(timeout=20)))
    except ValueError as error:
        return _private({'error': str(error)}, 400)
    except StorageError as error:
        return _private({'error': str(error)}, 503)


@csrf_protect
@admin_required
@require_POST
def migrate(request):
    try:
        if len(request.body) > 2_048:
            raise ValueError('Solicitud demasiado grande.')
        payload = json.loads(request.body or b'{}')
        if not isinstance(payload, dict):
            raise ValueError('Solicitud no válida.')
        ubigeo = registry_cloud.validate_district(
            str(payload.get('ubigeo') or '040126'))
        limit = payload.get('limit', 20)
        if type(limit) is not int:
            raise ValueError('El tamaño de tanda no es válido.')
        user = getattr(request, 'current_user', None) or request.user
        actor = (getattr(user, 'username', '') or
                 str(getattr(user, 'pk', 'administrador')))
        return _private(geollaqta_bulk.migrate_pending(
            Gateway(), ubigeo, limit, actor, R2(timeout=20)))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return _private({'error': str(error)}, 400)
    except StorageError as error:
        return _private({'error': str(error)}, 503)
