"""ACM facade for the shared master; enforce the active role on every request."""
import io
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_GET
from .access import required
from catastro import master
from catastro.storage import StorageError


@require_GET
@required('cadastral_info')
def configuration(request):
    try:
        response = JsonResponse(master.configuration())
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar la versión compartida del plano. Vuelve a consultar.'}, status=503)


@require_GET
@required('cadastral_info')
def revisions(request):
    from catastro import master_layers
    try:
        response = JsonResponse({'sources': master_layers.revisions()})
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar la versión compartida del plano.'}, status=503)


@require_GET
@required('cadastral_info')
def reference_geometry(request, source_id):
    from catastro import master_layers
    try:
        response = JsonResponse(master_layers.radius(source_id, request.GET.get('lat', ''),
            request.GET.get('lng', ''), request.GET.get('radius', '')),
            json_dumps_params={'separators': (',', ':')})
        response['Cache-Control'] = 'no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo leer el ajuste compartido. Vuelve a consultar.'}, status=503)
    except (ValueError, TypeError, OSError):
        return JsonResponse({'error': 'Fuente, ubicación o radio no válido.'}, status=400)


@require_GET
@required('cadastral_info')
def lot(request, lot_id):
    try:
        master.validate_lot(lot_id)
        from cuadrantizacion.geollaqta import report_response
        return report_response(lot_id, lot_id[:6], request.GET.get('record_id') or None, report_only=True)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)


@require_GET
@required('cadastral_info')
def facade(request, lot_id):
    try:
        from PIL import Image
        body = master.archived_facade(lot_id)
        if len(body) > 8_000_000:
            raise ValueError('Image too large')
        with Image.open(io.BytesIO(body)) as image:
            image.thumbnail((1200, 900))
            output = io.BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=85)
        response = HttpResponse(output.getvalue(), content_type='image/jpeg')
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (OSError, ValueError, RuntimeError):
        raise Http404


@require_GET
@required('cadastral_pdf')
@required('cadastral_info')
def report_pdf(request, lot_id):
    try:
        from catastro.map_report import report_pdf as original_pdf
        master.validate_lot(lot_id)
        body = original_pdf(lot_id, request.GET.get('record_id') or None)
        response = HttpResponse(body, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="reporte-catastral-{lot_id}.pdf"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except ValueError:
        return JsonResponse({'error': 'Lote o reporte catastral no válido.'}, status=400)
    except (OSError, RuntimeError):
        return JsonResponse({'error': 'El PDF catastral no está disponible. Vuelve a intentarlo.'}, status=502)
