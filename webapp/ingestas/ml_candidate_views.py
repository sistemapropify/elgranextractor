"""Read-only candidate control, integrated into the existing quality dashboard."""
import csv
from datetime import timedelta
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from .ml_candidates import schema_ready
from .ml_eligibility import LABELS, RULE_VERSION
from .models import MLCandidate, MLObservation, MLPipelineState, PropiedadesCompetencia


def authorized(request):
    user = getattr(request, 'current_user', None) or getattr(request, 'user', None)
    return bool(user and getattr(user, 'is_authenticated', False) and getattr(user, 'is_active', False))


def summary():
    counts = dict(MLCandidate.objects.values('status').annotate(n=Count('pk')).values_list('status', 'n'))
    total = PropiedadesCompetencia.objects.count()
    state = MLPipelineState.objects.filter(pk='candidates').first()
    heartbeat = state.heartbeat_at if state else None
    return dict(total=total, untracked=max(0, total - sum(counts.values())),
                statuses=[{'status': k, 'label': v, 'count': counts.get(k, 0)} for k, v in LABELS.items()],
                queue=MLObservation.objects.filter(status='pending').count(),
                worker_active=bool(heartbeat and heartbeat > timezone.now() - timedelta(minutes=3)),
                heartbeat=heartbeat, last_sweep=state.sweep_finished_at if state else None,
                cursor=state.cursor if state else 0,
                versions=MLObservation.objects.count(), model_trained=False)


def filtered(request):
    query = MLCandidate.objects.select_related('latest')
    for param, field in (('portal', 'propiedad__fuente'), ('tipo', 'propiedad__tipo_inmueble'),
                         ('distrito', 'propiedad__distrito'), ('precision', 'propiedad__precision_ubicacion'),
                         ('estado', 'status')):
        if request.GET.get(param):
            query = query.filter(**{field: request.GET[param]})
    if request.GET.get('trabajo'):
        job = request.GET['trabajo']
        query = query.filter(latest__job_id=int(job)) if job.isascii() and job.isdigit() and len(job) < 19 else query.none()
    if request.GET.get('cambio') == 'new':
        query = query.filter(latest__sequence=1)
    elif request.GET.get('cambio') == 'updated':
        query = query.filter(latest__sequence__gt=1)
    return query.order_by('-latest_id')


def safe_cell(value):
    text = '' if value is None else str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


@require_GET
@ensure_csrf_cookie
def dashboard(request):
    if not authorized(request):
        return HttpResponse('Inicia sesión para consultar las candidatas.', status=401)
    if not schema_ready():
        if request.GET.get('format') == 'summary':
            return JsonResponse({'ready': False}, status=503)
        return render(request, 'ingestas/property_quality.html', {'ml_mode': True, 'ml_ready': False}, status=503)
    if request.GET.get('format') == 'summary':
        return JsonResponse({'ready': True, **summary()})
    query = filtered(request)
    if request.GET.get('exportar') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="candidatas_entrenamiento.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Registro', 'Portal', 'Código', 'Versión', 'Trabajo de origen', 'Estado', 'Motivos',
                         'Precio USD', 'Terreno m2', 'Construcción m2', 'Antigüedad', 'Precisión', 'Distrito',
                         'Regla', 'Fecha de versión'])
        for c in query.iterator(chunk_size=200):
            s, o = c.latest.snapshot, c.latest
            values = [c.propiedad_id, s['fuente'], s['id_origen'], o.sequence, o.job_id, LABELS.get(c.status, c.status),
                      ' | '.join(r['message'] for r in o.reasons), s['precio_usd'], s['area_terreno'],
                      s['area_construida'], s['antiguedad_anios'], s['precision_ubicacion'], s['distrito'],
                      o.rule_version, o.created_at.isoformat()]
            writer.writerow([safe_cell(v) for v in values])
        return response
    page = Paginator(query, 50).get_page(request.GET.get('page'))
    for c in page:
        c.status_label = LABELS.get(c.status, c.status)
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('exportar', None)
    params['tab'] = 'entrenamiento'
    return render(request, 'ingestas/property_quality.html', dict(
        ml_mode=True, ml_ready=True, ml_summary=summary(), ml_page=page, ml_labels=LABELS.items(),
        filters=request.GET, params=params.urlencode(), rule_version=RULE_VERSION,
        portals=PropiedadesCompetencia.objects.order_by('fuente').values_list('fuente', flat=True).distinct(),
        types=PropiedadesCompetencia.TIPO_INMUEBLE_CHOICES))


@require_GET
def history(request, pk):
    if not authorized(request):
        return JsonResponse({'error': 'Inicia sesión.'}, status=401)
    if not schema_ready():
        return JsonResponse({'error': 'Migración pendiente.'}, status=503)
    query = MLObservation.objects.filter(propiedad_id=pk).order_by('-sequence')
    page = Paginator(query, 20).get_page(request.GET.get('page'))
    return JsonResponse({'record': pk, 'page': page.number, 'pages': page.paginator.num_pages,
        'versions': [{'sequence': o.sequence, 'created': o.created_at, 'status': LABELS.get(o.status, o.status),
                      'rule': o.rule_version, 'job': o.job_id, 'origin': o.origin,
                      'changes': o.changes, 'reasons': o.reasons, 'notes': o.notes,
                      'evidence': o.snapshot.get('evidence')} for o in page]})
