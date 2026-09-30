import csv
import hashlib
import json
from decimal import Decimal
from django import forms
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from cuadrantizacion.views import PrometeoSessionAuthentication
from .models import (PropiedadesCompetencia, RevisionPropiedadScraping,
                     CambioPropiedadScraping, RevisionIAAlerta)
from .property_quality import DATA_FIELDS, analyze, number

EDIT_FIELDS = ('titulo', 'tipo_inmueble', 'tipo_operacion', 'precio_soles', 'precio_usd',
    'area_m2', 'area_terreno', 'area_construida', 'dormitorios', 'banos', 'estacionamientos',
    'distrito', 'provincia', 'departamento', 'direccion_texto', 'latitud', 'longitud',
    'precision_ubicacion', 'descripcion', 'amenities', 'url', 'imagen_url',
    'antiguedad_anios', 'agencia_agente')

class PropertyForm(forms.ModelForm):
    class Meta:
        model = PropiedadesCompetencia
        fields = EDIT_FIELDS

    def clean(self):
        data = super().clean()
        for key in ('precio_soles', 'precio_usd', 'area_m2', 'area_terreno', 'area_construida'):
            if data.get(key) is not None and data[key] <= 0:
                self.add_error(key, 'Debe ser mayor que cero o quedar vacío.')
        for key in ('dormitorios', 'banos', 'estacionamientos', 'antiguedad_anios'):
            if data.get(key) is not None and data[key] < 0:
                self.add_error(key, 'No puede ser negativo.')
        for key, limit in (('latitud', 90), ('longitud', 180)):
            if data.get(key) is not None and not -limit <= data[key] <= limit:
                self.add_error(key, 'Coordenada fuera de rango.')
        if (data.get('latitud') is None) != (data.get('longitud') is None):
            self.add_error('latitud', 'Completa ambas coordenadas o deja ambas vacías.')
        return data

from .property_access import user_for, allowed

def value(v):
    return str(v) if isinstance(v, Decimal) or hasattr(v, 'isoformat') else v

def snapshot(obj, revision):
    data = {field.name: value(field.value_from_object(obj)) for field in obj._meta.concrete_fields}
    data.update(excluida=revision.excluida, motivo=revision.motivo,
                campos_protegidos=revision.campos_protegidos,
                correcta=revision.correcta)
    return data

def version(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

def alertas_para(obj, revision, revision_ia):
    """Reproduce, para un solo registro, las alertas del dashboard.

    La comparacion de atipicos de la tabla se calcula contra el grupo
    comparable del distrito; por eso no basta con analizar la fila sola.
    """
    district = (obj.distrito or '').strip()
    scope = Q(distrito__iexact=district)
    if not district:
        scope |= Q(distrito__isnull=True)
    rows = list(PropiedadesCompetencia.objects.filter(scope).values(*DATA_FIELDS))
    revisions = {r.propiedad_id: r for r in
                 RevisionPropiedadScraping.objects.filter(propiedad_id__in=[r['id'] for r in rows])}
    for row in rows:
        rev = revisions.get(row['id'])
        row['excluida'] = bool(rev and rev.excluida)
        row['motivo'] = rev.motivo if rev else ''
    current = next((r for r in analyze(rows) if r['id'] == obj.pk), None)
    return {
        'alertas': (current or {}).get('alertas') or [],
        'quality_status': (current or {}).get('quality_status'),
        'ia_veredicto': revision_ia.veredicto if revision_ia else None,
        'ia_motivo': revision_ia.motivo if revision_ia else '',
        'ia_correccion': revision_ia.correccion if revision_ia else {},
    }

class PropertyEditor(APIView):
    authentication_classes = [PrometeoSessionAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = get_object_or_404(PropiedadesCompetencia, pk=pk)
            revision = RevisionPropiedadScraping.objects.filter(propiedad=obj).first() or RevisionPropiedadScraping(propiedad=obj)
            revision_ia = RevisionIAAlerta.objects.filter(propiedad=obj).first()
            data = snapshot(obj, revision)
            return Response({'html': PropertyForm(instance=obj).as_p(), 'record': data,
                             'version': version(data), 'can_edit': allowed(request.user),
                             'alertas': alertas_para(obj, revision, revision_ia)})
        except Http404:
            raise
        except Exception as exc:
            return Response({'error': f'Error al cargar el registro: {exc}'}, status=500)

    def post(self, request, pk):
        if not allowed(request.user):
            return Response({'error': 'Se requiere permiso para editar propiedades scrapeadas.'}, status=403)
        try:
            with transaction.atomic():
                obj = get_object_or_404(PropiedadesCompetencia.objects.select_for_update(), pk=pk)
                revision, _ = RevisionPropiedadScraping.objects.get_or_create(propiedad=obj)
                before = snapshot(obj, revision)
                if request.data.get('version') != version(before):
                    return Response({'error': 'El registro cambió. Cierra y vuelve a abrir para revisar los datos actuales.'}, status=409)
                form = PropertyForm(request.data, instance=obj)
                if not form.is_valid():
                    return Response({'error': 'Revisa los campos indicados.', 'fields': form.errors}, status=400)
                revision.excluida = request.data.get('excluida') == 'true'
                revision.motivo = str(request.data.get('motivo') or '').strip()
                revision.correcta = request.data.get('correcta') == 'true'
                revision.corregida_en = timezone.now() if revision.correcta else None
                if revision.excluida and not revision.motivo:
                    return Response({'error': 'Indica el motivo para excluir el registro.'}, status=400)
                changed = set(form.changed_data)
                # Keep the legacy primary surface aligned after a manual area/type edit.
                if changed.intersection({'area_terreno', 'area_construida', 'tipo_inmueble'}):
                    obj.area_m2 = (obj.area_terreno or obj.area_construida) if obj.tipo_inmueble == 'Terreno' else (obj.area_construida or obj.area_terreno)
                    changed.add('area_m2')
                revision.campos_protegidos = sorted(set(revision.campos_protegidos) | changed)
                obj.save()
                revision.save()
                after = snapshot(obj, revision)
                changes = {k: {'antes': before[k], 'despues': after[k]} for k in after if before[k] != after[k]}
                CambioPropiedadScraping.objects.create(propiedad=obj,
                    usuario=str(getattr(request.user, 'username', request.user.pk)), cambios=changes)
            return Response({'ok': True, 'message': 'Registro guardado. Las correcciones quedan protegidas frente al scraper.'})
        except Http404:
            raise
        except Exception as exc:
            return Response({'error': f'Error al guardar el registro: {exc}'}, status=500)

@ensure_csrf_cookie
def dashboard(request):
    if request.GET.get('tab') == 'contexto':
        from .ml_context_views import dashboard as context_dashboard
        return context_dashboard(request)
    if request.GET.get('tab') == 'entrenamiento':
        from .ml_candidate_views import dashboard as candidates_dashboard
        return candidates_dashboard(request)
    user = user_for(request)
    if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return HttpResponse('Inicia sesión para consultar la calidad.', status=401)
    query = PropiedadesCompetencia.objects.all()
    for param, field in (('portal', 'fuente'), ('tipo', 'tipo_inmueble'), ('distrito', 'distrito'), ('operacion', 'tipo_operacion')):
        if request.GET.get(param):
            query = query.filter(**{field: request.GET[param]})
    if request.GET.get('pub_estado'):
        query = query.filter(estado_publicacion=request.GET['pub_estado'])
    revisions = {r.propiedad_id: r for r in RevisionPropiedadScraping.objects.all()}
    revisiones_ia = {r.propiedad_id: r for r in RevisionIAAlerta.objects.all()}
    rows = []
    for row in query.values(*DATA_FIELDS).order_by('id').iterator(chunk_size=1000):
        revision = revisions.get(row['id'])
        row['excluida'] = bool(revision and revision.excluida)
        row['correcta'] = bool(revision and revision.correcta)
        row['motivo'] = revision.motivo if revision else ''
        ia = revisiones_ia.get(row['id'])
        row['ia_veredicto'] = ia.veredicto if ia else None
        row['ia_motivo'] = ia.motivo if ia else ''
        row['ia_correccion'] = ia.correccion if ia else {}
        rows.append(row)
    rows = analyze(rows)
    summary = {'total': len(rows), 'con_alertas': sum(bool(r['alertas']) for r in rows),
               'excluidas': sum(r['excluida'] for r in rows),
               'correctas': sum(1 for r in rows if r['correcta']),
               'ia_real': sum(1 for r in rows if r['ia_veredicto'] == 'real'),
               'ia_ruido': sum(1 for r in rows if r['ia_veredicto'] == 'ruido'),
               'ia_dudoso': sum(1 for r in rows if r['ia_veredicto'] == 'dudoso'),
               'ia_sin_revisar': sum(1 for r in rows if r['alertas'] and not r['ia_veredicto'])}
    # Barra de progreso del triaje: cuantas sospechosas ya tienen veredicto.
    summary['triaje_total'] = summary['con_alertas']
    summary['triaje_revisados'] = summary['con_alertas'] - summary['ia_sin_revisar']
    state = request.GET.get('estado', 'alertas')
    if state == 'alertas':
        rows = [r for r in rows if r['alertas'] and not r['correcta']]
    elif state == 'correctas':
        rows = [r for r in rows if r['correcta']]
    elif state == 'excluidas':
        rows = [r for r in rows if r['excluida']]
    elif state in ('ia_real', 'ia_ruido', 'ia_dudoso'):
        rows = [r for r in rows if r['ia_veredicto'] == state[3:]]
    elif state == 'ia_pendiente':
        rows = [r for r in rows if r['alertas'] and not r['ia_veredicto']]
    elif state in ('outlier', 'incomplete', 'review'):
        rows = [r for r in rows if r['quality_status'] == state]
    if request.GET.get('exportar') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="calidad_propiedades.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow([*DATA_FIELDS, 'excluida', 'motivo', 'alertas'])
        for row in rows:
            cells = [row.get(k) for k in DATA_FIELDS] + [row['excluida'], row['motivo'], ' | '.join(row['alertas'])]
            writer.writerow(["'" + c if isinstance(c, str) and c.startswith(('=', '+', '-', '@')) else c for c in cells])
        return response
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'ingestas/property_quality.html', {
        'summary': summary, 'page': Paginator(rows, 50).get_page(request.GET.get('page')),
        'params': params.urlencode(), 'filters': request.GET,
        'portals': PropiedadesCompetencia.objects.order_by('fuente').values_list('fuente', flat=True).distinct(),
        'types': PropiedadesCompetencia.TIPO_INMUEBLE_CHOICES,
        'estados_publicacion': PropiedadesCompetencia.ESTADO_PUBLICACION_CHOICES,
        'can_edit': allowed(user),
    })


def disparar_triage(request):
    """Dispara el triaje de IA sobre las alertas pendientes, en segundo plano.

    Devuelve JSON; el analisis corre en un hilo daemon, asi que la respuesta es
    inmediata y los veredictos van apareciendo en el dashboard a medida que se
    guardan. La primera vez procesa todo el historico; despues solo lo nuevo.
    """
    from ingestas.calidad_ia import lanzar_triage_en_background, propiedades_con_alertas

    if not allowed(user_for(request)):
        return JsonResponse({'error': 'Se requiere permiso para disparar el triaje.'}, status=403)
    pendientes = len(propiedades_con_alertas(sin_veredicto=True))
    lanzar_triage_en_background()
    return JsonResponse({'ok': True, 'pendientes': pendientes,
                         'mensaje': f'Triaje lanzado: {pendientes} propiedades por analizar.'})
