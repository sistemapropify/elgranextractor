"""ACM facade for the shared master; enforce the active role on every request."""
import io
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_GET
from .access import required
from catastro import master


@require_GET
@required('cadastral_info')
def configuration(request):
    return JsonResponse(master.configuration())


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
