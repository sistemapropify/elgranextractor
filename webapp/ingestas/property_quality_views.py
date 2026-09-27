import csv
import hashlib
import json
from decimal import Decimal
from django import forms
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from cuadrantizacion.views import PrometeoSessionAuthentication
from .models import PropiedadesCompetencia, RevisionPropiedadScraping, CambioPropiedadScraping
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

def user_for(request):
    return getattr(request, 'current_user', None) or getattr(request, 'user', None)

def allowed(user):
    return bool(user and getattr(user, 'is_active', False) and
                (getattr(user, 'is_staff', False) or user.has_perm('ingestas.change_propiedadescompetencia')))

def value(v):
    return str(v) if isinstance(v, Decimal) or hasattr(v, 'isoformat') else v

def snapshot(obj, revision):
    data = {field.name: value(field.value_from_object(obj)) for field in obj._meta.concrete_fields}
    data.update(excluida=revision.excluida, motivo=revision.motivo,
                campos_protegidos=revision.campos_protegidos)
    return data

def version(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

class PropertyEditor(APIView):
    authentication_classes = [PrometeoSessionAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        obj = get_object_or_404(PropiedadesCompetencia, pk=pk)
        revision = RevisionPropiedadScraping.objects.filter(propiedad=obj).first() or RevisionPropiedadScraping(propiedad=obj)
        data = snapshot(obj, revision)
        return Response({'html': PropertyForm(instance=obj).as_p(), 'record': data,
                         'version': version(data), 'can_edit': allowed(request.user)})

    def post(self, request, pk):
        if not allowed(request.user):
            return Response({'error': 'Se requiere permiso para editar propiedades scrapeadas.'}, status=403)
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

@ensure_csrf_cookie
def dashboard(request):
    user = user_for(request)
    if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return HttpResponse('Inicia sesión para consultar la calidad.', status=401)
    query = PropiedadesCompetencia.objects.all()
    for param, field in (('portal', 'fuente'), ('tipo', 'tipo_inmueble'), ('distrito', 'distrito'), ('operacion', 'tipo_operacion')):
        if request.GET.get(param):
            query = query.filter(**{field: request.GET[param]})
    revisions = {r.propiedad_id: r for r in RevisionPropiedadScraping.objects.all()}
    rows = []
    for row in query.values(*DATA_FIELDS).order_by('id').iterator(chunk_size=1000):
        revision = revisions.get(row['id'])
        row['excluida'] = bool(revision and revision.excluida)
        row['motivo'] = revision.motivo if revision else ''
        rows.append(row)
    rows = analyze(rows)
    summary = {'total': len(rows), 'con_alertas': sum(bool(r['alertas']) for r in rows),
               'excluidas': sum(r['excluida'] for r in rows)}
    state = request.GET.get('estado', 'alertas')
    if state == 'alertas':
        rows = [r for r in rows if r['alertas']]
    elif state == 'excluidas':
        rows = [r for r in rows if r['excluida']]
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
        'can_edit': allowed(user),
    })
