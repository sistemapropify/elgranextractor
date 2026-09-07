"""Version publication shared by the control panel and the Android release pipeline."""
import json
import re
from urllib.parse import urlsplit

from django import forms
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden, StreamingHttpResponse, Http404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from lead_intelligence.control_access import control_required
from lead_intelligence.control_notifications import enabled
from lead_intelligence.control_runtime import runtime_status
from lead_intelligence.remarketing_gateway import config
from lead_intelligence.models import LeadControlMember, LeadControlNotice
from .models import MobileAppVersion, MobileNotificationDevice


@require_GET
def mobile_schema_health(request):
    """Health check used by Azure after deployment of the mobile API schema."""
    try:
        # Query both tables that back registration and update delivery. This
        # verifies that the migrations required by the APK are available.
        MobileNotificationDevice.objects.exists()
        MobileAppVersion.objects.exists()
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


@require_GET
def download_apk(request, asset_id):
    """Expose only published installers; keep the private GitHub token on the server."""
    path = f'/prospects/api/mobile/apk/{asset_id}/'
    if not MobileAppVersion.objects.filter(published=True, download_url__endswith=path).exists():
        raise Http404()
    token = config('MOBILE_APP_GITHUB_TOKEN')
    if not token:
        return JsonResponse({'error': 'La descarga de APK no está configurada.'}, status=503)
    import requests
    try:
        response = requests.get(f'https://api.github.com/repos/sistemapropify/propitools/releases/assets/{asset_id}', headers={
            'Authorization': f'Bearer {token}', 'Accept':'application/octet-stream', 'X-GitHub-Api-Version':'2022-11-28'}, stream=True, timeout=(5,30))
        if response.status_code != 200 or 'json' in response.headers.get('Content-Type', ''):
            response.close()
            return JsonResponse({'error':'No se pudo obtener el instalador publicado.'}, status=502)
    except requests.RequestException:
        return JsonResponse({'error':'El servicio de descarga no está disponible.'}, status=502)
    def chunks():
        try:
            yield from response.iter_content(65536)
        finally:
            response.close()
    result = StreamingHttpResponse(chunks(), content_type='application/vnd.android.package-archive')
    result['Content-Disposition'] = 'attachment; filename="propitools.apk"'
    result['X-Content-Type-Options'] = 'nosniff'
    return result


class ReleaseForm(forms.ModelForm):
    class Meta:
        model = MobileAppVersion
        fields = ['version_code', 'version_name', 'download_url', 'sha256', 'min_supported_version_code', 'force_update', 'release_notes']
        labels = {'version_code': 'Número de compilación', 'version_name': 'Nombre de versión', 'min_supported_version_code': 'Versión mínima admitida', 'release_notes': 'Cambios de esta versión'}

    def clean(self):
        data = super().clean()
        version, minimum = data.get('version_code'), data.get('min_supported_version_code')
        if version is not None and not 1 <= version <= 2100000000:
            self.add_error('version_code', 'Usa un número entre 1 y 2100000000.')
        if minimum is not None and (minimum < 1 or version is not None and minimum > version):
            self.add_error('min_supported_version_code', 'Debe estar entre 1 y el número de compilación.')
        url = urlsplit(data.get('download_url') or '')
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            self.add_error('download_url', 'Publica una URL HTTPS directa al APK, sin credenciales.')
        sha = (data.get('sha256') or '').strip().lower()
        if not re.fullmatch('[a-f0-9]{64}', sha):
            self.add_error('sha256', 'Copia la huella SHA-256 calculada para ese APK.')
        data['sha256'] = sha
        return data


@csrf_exempt
@require_POST
def publish_api(request):
    """Register a release published by the Propitools GitHub workflow.

    The workflow sends its repository-scoped fine-grained token.  We verify it
    against the Propitools repository instead of duplicating that secret in
    Azure, where it would need manual rotation in two places.
    """
    authorization = request.headers.get('Authorization', '')
    token = authorization.removeprefix('Bearer ').strip() if authorization.startswith('Bearer ') else ''
    if len(token) < 32:
        return JsonResponse({'ok': False, 'error': 'No autorizado.'}, status=403)
    import requests
    try:
        verification = requests.get(
            'https://api.github.com/repos/sistemapropify/propitools',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'},
            timeout=(5, 15),
        )
        authorized = verification.status_code == 200
        verification.close()
    except requests.RequestException:
        authorized = False
    if not authorized:
        return JsonResponse({'ok': False, 'error': 'No autorizado.'}, status=403)
    if len(request.body) > 20000:
        return JsonResponse({'ok': False, 'error': 'Publicación demasiado grande.'}, status=413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido.'}, status=400)
    with transaction.atomic():
        try:
            version = int(data.get('version_code', 0))
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': 'Compilación inválida.'}, status=400)
        existing = MobileAppVersion.objects.select_for_update().filter(version_code=version).first()
        if existing:
            if existing.published and existing.sha256 == str(data.get('sha256', '')).lower() and existing.download_url == data.get('download_url'):
                return JsonResponse({'ok': True, 'version_code': existing.version_code, 'already_published': True})
            return JsonResponse({'ok': False, 'error': 'Ese número ya existe con otra publicación.'}, status=409)
        form = ReleaseForm(data)
        if not form.is_valid():
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        release = form.save(commit=False)
        release.published, release.published_at = True, timezone.now()
        release.save()
    return JsonResponse({'ok': True, 'version_code': release.version_code}, status=201)


@control_required
@require_http_methods(['GET', 'POST'])
def updates(request):
    access = request.control_access
    if not access.configures:
        return HttpResponseForbidden('Solo gerencia puede publicar actualizaciones.')
    form = ReleaseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        release = form.save(commit=False)
        release.published, release.published_at = True, timezone.now()
        release.save()
        return redirect('analisis_crm:mobile_updates')
    return render(request, 'prospects/app_updates.html', {
        'access': access, 'form': form, 'versions': MobileAppVersion.objects.all()[:20],
        'device_count': MobileNotificationDevice.objects.filter(active=True).count(),
        'member_count': LeadControlMember.objects.filter(active=True).exclude(mobile_identity_id='').count(),
        'push_enabled': enabled('LEAD_CONTROL_PUSH_ENABLED'),
        'firebase_configured': bool(config('LEAD_CONTROL_FIREBASE_PROJECT_ID')),
        'firebase_credential_configured': bool(config('GOOGLE_APPLICATION_CREDENTIALS')),
        'publish_configured': True,
        'accepted_count': LeadControlNotice.objects.filter(channel='push', status='accepted').count(),
        'uncertain_count': LeadControlNotice.objects.filter(channel='push', status='uncertain').count(),
    })
