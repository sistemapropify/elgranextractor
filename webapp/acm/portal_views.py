"""Propify login, scoped history, role settings and perspective controls."""
import hashlib
import ipaddress
import json
import socket
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .access import (CATEGORIES, DEFAULTS, SESSION_PREVIEW, SESSION_PROFILE, SESSION_TOKEN,
                     database, get_access, policy_for, required, role_catalog, set_perspective, template_context)
from .access_data import photo_digest, project, unseal
from .access_models import ACMPhotoReview, ACMPortalAnalysis, ACMRoleAudit, ACMRolePolicy
from .history_access import visible_history, attach_authors


@csrf_protect
@require_http_methods(['GET', 'POST'])
def login(request):
    destination = request.POST.get('next') or request.GET.get('next') or '/acm/'
    if not url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure()) or not destination.startswith('/acm/'):
        destination = '/acm/'
    error = ''
    username = ''
    if request.method == 'POST':
        username = str(request.POST.get('username', '')).strip()
        password = request.POST.get('password', '')
        if not username or not password:
            error = 'Ingresa tu usuario y contraseña de Propify.'
        else:
            try:
                last_error = 'No se pudo conectar con Propify. Inténtalo nuevamente.'
                primary = settings.PROPIFY_AUTH_TOKEN_URL
                urls = [primary]
                if 'api.propify.pe' in primary:
                    urls.append(primary.replace('api.propify.pe', 'app.propify.pe'))
                elif 'app.propify.pe' in primary:
                    urls.append(primary.replace('app.propify.pe', 'api.propify.pe'))
                for url in urls:
                    try:
                        response = requests.post(url, json={'username': username, 'password': password}, timeout=15,
                                                 headers={'Accept': 'application/json'}, allow_redirects=False)
                    except requests.RequestException:
                        continue
                    if response.status_code in (400, 401, 403):
                        raise ValueError('Usuario o contraseña incorrectos.')
                    if response.status_code not in (200, 201):
                        continue
                    data = response.json()
                    if not isinstance(data, dict):
                        continue
                    token = data.get('access') or data.get('token')
                    if not isinstance(token, str) or not token:
                        continue
                    profile = data.get('user', data)
                    if not isinstance(profile, dict):
                        continue
                    if not str(profile.get('id') or profile.get('pk') or '').isdigit():
                        remote = requests.get(settings.PROPIFY_AUTH_ME_URL, headers={'Authorization': 'Bearer '+token}, timeout=15, allow_redirects=False)
                        if remote.status_code != 200:
                            continue
                        payload = remote.json()
                        profile = payload.get('user', payload) if isinstance(payload, dict) else {}
                    if not isinstance(profile, dict):
                        continue
                    if not str(profile.get('id') or profile.get('pk') or '').isdigit():
                        raise ValueError('Propify no devolvió el identificador del usuario.')
                    request.session.cycle_key()
                    request.session[SESSION_TOKEN] = token
                    request.session[SESSION_PROFILE] = {key: profile.get(key) for key in ('id', 'pk', 'username')}
                    request.session.pop(SESSION_PREVIEW, None)
                    request.session.pop('acm_logged_out', None)
                    request.session.set_expiry(60 * 60 * 24 * 30)
                    return redirect(destination)
                error = last_error
            except (ValueError, requests.RequestException) as exc:
                error = 'Usuario o contraseña incorrectos.' if str(exc) == 'Usuario o contraseña incorrectos.' else 'No se pudo validar la sesión de Propify. Reintenta.'
    response = render(request, 'acm/portal_login.html', {'error': error, 'username': username, 'next': destination})
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@csrf_protect
def logout(request):
    request.session.flush()
    request.session['acm_logged_out'] = True
    return redirect('acm:login')


@required(page=True)
def dashboard(request):
    rows = visible_history(request)
    context = template_context(request)
    context.update({'analysis_count': rows.count(), 'recent': attach_authors(rows[:5], request.acm_access.user)})
    return render(request, 'acm/portal_dashboard.html', context)


@required('history', page=True)
def history(request):
    rows = visible_history(request)
    context = template_context(request)
    context['history_page'] = Paginator(rows, 25).get_page(request.GET.get('page'))
    context['history_page'].object_list = attach_authors(context['history_page'].object_list, request.acm_access.user)
    return render(request, 'acm/portal_history.html', context)


@require_POST
@csrf_protect
@required('history')
def delete_analysis(request, uuid):
    row = get_object_or_404(ACMPortalAnalysis.objects.using(database()), id=uuid, owner_id=request.acm_access.user.pk)
    row.delete(using=database())
    return redirect('acm:historial_acm')


@require_POST
@csrf_protect
@required()
def perspective(request):
    if not request.acm_access.can_preview:
        raise PermissionDenied
    from .role_analysis import SESSION_ANALYSIS, saved_analysis, selection_ui, remember_analysis
    saved = None
    try:
        role_id = int(request.POST.get('role_id') or 0)
        payload = request.POST.get('analysis_selection')
        if payload:
            from .components_views import _signed_selection
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError('Invalid selection')
            flags = request.acm_access.permissions
            if data.get('manual_valuation') is not None and not flags['adjust_valuation']:
                raise PermissionDenied
            if data.get('report_notes') and not flags['report_notes']:
                raise PermissionDenied
            if data.get('target_areas') is not None and not flags['adjust_areas']:
                raise PermissionDenied
            state, excluded = _signed_selection(request, data)
            saved = dict(state=state, excluded=excluded,
                         ui=selection_ui(request, state, data.get('ui', {})))
        elif request.POST.get('analysis_view'):
            saved = saved_analysis(request, request.POST['analysis_view'])
        set_perspective(request, role_id)
        if saved:
            key = remember_analysis(request, saved['state'], saved['excluded'], saved['ui'])
            return redirect('/acm/analisis/?analysis_view=' + key)
        request.session.pop(SESSION_ANALYSIS, None)
    except signing.BadSignature:
        return JsonResponse({'error': 'El análisis venció o cambió su acceso. Vuelve a buscar antes de cambiar de vista.'}, status=409)
    except (ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({'error': 'No se pudo cambiar de vista. Revisa el rol y el análisis.'}, status=400)
    return redirect('acm:acm_analisis')


@csrf_protect
@required(page=True)
def role_settings(request):
    if not request.acm_access.can_configure:
        raise PermissionDenied
    if request.method != 'GET':
        return HttpResponse(status=405)
    context = template_context(request)
    context['categories'] = [{'name': name, 'items': [{'key': key, 'label': label} for key, label, _ in items]} for name, items in CATEGORIES]
    return render(request, 'acm/role_settings.html', context)


@csrf_protect
@require_http_methods(['GET', 'POST'])
@required()
def role_policy(request, role_id):
    if not request.acm_access.can_configure:
        raise PermissionDenied
    role = next((role for role in role_catalog() if role['id'] == role_id), None)
    if role is None:
        raise Http404
    if request.method == 'GET':
        values, revision = policy_for(role)
        return JsonResponse({'permissions': values, 'revision': revision, 'locked': role['name'].strip().casefold() == 'administrador'})
    if role['name'].strip().casefold() == 'administrador':
        return JsonResponse({'error': 'Administrador conserva todas las funcionalidades.'}, status=400)
    try:
        data = json.loads(request.body)
        values = data['permissions']
        revision = data['revision']
        if not isinstance(values, dict) or set(values) != set(DEFAULTS) or any(type(v) is not bool for v in values.values()) or type(revision) is not int:
            raise ValueError
        if not values['portal_names'] and any(values[key] for key in ('portal_pins', 'publication', 'portal_link')):
            return JsonResponse({'error': 'Los logos y enlaces requieren permitir el nombre del portal.'}, status=400)
        if not values['property_data'] and any(values[key] for key in ('property_pins', 'photos', 'calculate')):
            return JsonResponse({'error': 'Pines, fotografías y cálculo requieren habilitar los datos de la propiedad.'}, status=400)
        if values['pdm_card'] and not values['pdm_query']:
            return JsonResponse({'error': 'La tarjeta PDM requiere habilitar la consulta de zonificación.'}, status=400)
        with transaction.atomic(using=database()):
            row = ACMRolePolicy.objects.using(database()).select_for_update().filter(role_id=role_id).first()
            if (row.revision if row else 0) != revision:
                return JsonResponse({'error': 'Otra persona cambió esta configuración. Recarga el rol antes de guardar.'}, status=409)
            before = row.permissions if row else dict(DEFAULTS)
            if row is None:
                row = ACMRolePolicy(role_id=role_id)
            row.permissions = values
            row.revision = revision + 1
            row.updated_by = request.acm_access.user.pk
            row.save(using=database())
            ACMRoleAudit.objects.using(database()).create(role_id=role_id, actor_id=request.acm_access.user.pk, before=before, after=values)
        return JsonResponse({'ok': True, 'revision': revision + 1})
    except IntegrityError:
        return JsonResponse({'error': 'La configuración cambió. Recarga el rol.'}, status=409)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': 'Configuración inválida.'}, status=400)


@require_GET
@required('pdm_polygons')
def map_layers(request):
    from cuadrantizacion.map_layers import map_layers_config
    return JsonResponse(map_layers_config(include_zones=True))


@require_GET
@required('pdm_query')
def pdm_query(request):
    from cuadrantizacion.views import api_clasificar_zonificacion
    return api_clasificar_zonificacion(request)


@require_POST
@csrf_protect
@required('ai')
def model_estimate(request):
    # Adapt the published model reader without creating a Prometeo account/session.
    from ingestas.ml_model_views import estimate
    previous = getattr(request, 'current_user', None)
    request.current_user = request.acm_identity
    try:
        response = estimate(request)
    finally:
        request.current_user = previous
    if response.status_code == 200 and not request.acm_access.permissions['metadata']:
        data = json.loads(response.content)
        for key in ('run_id', 'dataset_id', 'sample'):
            data.pop(key, None)
        return JsonResponse(data)
    return response


def _photo_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    storage = str(getattr(settings, 'AZURE_ACCOUNT_NAME', 'granextractormedia')) + '.blob.core.windows.net'
    allowed = {'remax.pe', 'www.remax.pe', 'properati.com.pe', 'www.properati.com.pe', storage,
               'propifymedia01.blob.core.windows.net', 'images.properati.com',
               'img10.naventcdn.com'}
    allowed.update(getattr(settings, 'ACM_PHOTO_HOSTS', ()))
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or host not in allowed:
        raise ValueError('image host')
    for address in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ValueError('image address')
    return url


def load_photo_bytes(url):
    """Validated image download shared by browser delivery and PDF embedding."""
    import io
    from PIL import Image
    from cuadrantizacion.views import _map_image_url
    storage = str(getattr(settings, 'AZURE_ACCOUNT_NAME', 'granextractormedia')) + '.blob.core.windows.net'
    if urlsplit(url).hostname == storage:
        url = _map_image_url(url)
    with requests.get(_photo_url(url), stream=True, timeout=(4, 10), allow_redirects=False) as source:
        if source.status_code != 200 or source.headers.get('Content-Type', '').split(';')[0] not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
            raise ValueError('image response')
        content = bytearray()
        for part in source.iter_content(65536):
            content.extend(part)
            if len(content) > 8 * 1024 * 1024:
                raise ValueError('image size')
    with Image.open(io.BytesIO(content)) as original:
        original.thumbnail((1600, 1600))
        stream = io.BytesIO()
        original.convert('RGB').save(stream, format='JPEG', quality=88)
    return stream.getvalue()


@require_GET
@required('photos')
def photo(request, ticket):
    try:
        item = unseal(ticket)
        if item.get('kind') != 'photo' or item.get('scope') != request.acm_access.fingerprint:
            raise ValueError
        url = item['url']
        if not request.acm_access.permissions['unreviewed_photos'] and not ACMPhotoReview.objects.using(database()).filter(digest=photo_digest(url), approved=True).exists():
            raise ValueError
        response = HttpResponse(load_photo_bytes(url), content_type='image/jpeg')
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (signing.BadSignature, ValueError, KeyError, requests.RequestException, OSError):
        raise Http404


@require_POST
@csrf_protect
@required()
def review_photo(request):
    if not request.acm_access.can_configure:
        raise PermissionDenied
    try:
        data = json.loads(request.body)
        item = unseal(data['ticket'])
        if item.get('kind') != 'photo' or item.get('scope') != request.acm_access.fingerprint or type(data['approved']) is not bool:
            raise ValueError
        ACMPhotoReview.objects.using(database()).update_or_create(digest=photo_digest(item['url']), defaults={
            'approved': data['approved'], 'reviewed_by': request.acm_access.user.pk})
        return JsonResponse({'ok': True})
    except (ValueError, KeyError, TypeError, signing.BadSignature):
        return JsonResponse({'error': 'Fotografía inválida. Repite la búsqueda.'}, status=400)
