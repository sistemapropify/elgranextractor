"""Export a frozen training-candidate snapshot, with one audit row per record."""
import csv

from django.http import HttpResponse
from django.views.decorators.http import require_GET

from .ml_candidate_views import authorized, safe_cell
from .ml_dataset import schema_ready
from .models import MLDatasetSnapshot, MLDatasetEntry


@require_GET
def dataset_export(request, pk):
    if not authorized(request):
        return HttpResponse('Inicia sesión para exportar el conjunto.', status=401)
    if not schema_ready():
        return HttpResponse('La migración de conjuntos aún está pendiente.', status=503)
    dataset = MLDatasetSnapshot.objects.filter(pk=pk).first()
    if not dataset:
        return HttpResponse('No existe esa versión del conjunto.', status=404)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ofertas-ml-v%d.csv"' % pk
    response['Cache-Control'] = 'private, no-store'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Versión conjunto', 'Incluido', 'Motivo', 'Registro', 'Portal', 'Código',
        'URL publicación', 'Tipo', 'Operación', 'Precio oferta USD', 'Terreno m²',
        'Construcción m²', 'Antigüedad', 'Dormitorios', 'Baños', 'Latitud', 'Longitud',
        'Precisión fuente', 'Microzona', 'Versión microzona', 'Hash grupo identidad',
        'Versión observación', 'Regla espacial', 'Fecha de corte'])
    entries = MLDatasetEntry.objects.filter(dataset=dataset).select_related(
        'observation', 'spatial_assessment').order_by('candidate_id')
    for entry in entries.iterator(chunk_size=200):
        item = entry.features
        writer.writerow([safe_cell(v) for v in (
            dataset.pk, 'sí' if entry.included else 'no', entry.reason, entry.candidate_id,
            item.get('fuente'), item.get('id_origen'), item.get('url'), item.get('tipo_inmueble'),
            item.get('tipo_operacion'), entry.target_price_usd, item.get('area_terreno'),
            item.get('area_construida'), item.get('antiguedad_anios'), item.get('dormitorios'),
            item.get('banos'), item.get('latitud'), item.get('longitud'),
            item.get('precision_ubicacion'), item.get('zone_name'), item.get('zone_version'),
            entry.identity_group_hash, entry.observation.sequence,
            entry.spatial_assessment.rule_version if entry.spatial_assessment_id else '',
            dataset.created_at.isoformat())])
    return response
