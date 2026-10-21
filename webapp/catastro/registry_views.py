"""Admin-only table, filters, exports and immutable original document links."""
import csv
import hashlib
import io
import json
import re
import sqlite3

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import registry, registry_cloud
from .storage import R2, StorageError
from .views import admin_required


def private(response):
    response['Cache-Control'] = 'private, no-store'
    response['Vary'] = 'Cookie'
    return response


@require_GET
@admin_required
@ensure_csrf_cookie
def table(request):
    from scrapi.geollaqta_scraper import DISTRICTS
    return private(render(request,'catastro/registry.html',{'districts':list(DISTRICTS.values()),
                          'columns':registry.COLUMNS,'number_columns':registry.NUMBER_COLUMNS}))


@require_GET
@admin_required
def records(request):
    try:
        db, _ = registry_cloud.load(request.GET.get('ubigeo','040126'))
        try:
            result=registry.query(db,request.GET)
        finally:
            db.close()
        return private(JsonResponse(result))
    except ValueError as error:
        return private(JsonResponse({'error':str(error)},status=400))
    except (StorageError, sqlite3.DatabaseError):
        return private(JsonResponse({'error':'No se pudo consultar el índice tabular de R2.'},status=503))


@require_POST
@admin_required
def synchronize(request):
    from .master_pipeline import status as pipeline_status
    if not pipeline_status()['historical_migration_enabled']:
        return private(JsonResponse({'error':'La migración histórica de JSON a tablas permanece detenida por indicación del usuario.'},status=409))
    if len(request.body)>8_000:
        return private(JsonResponse({'error':'Solicitud demasiado grande.'},status=413))
    try:
        data=json.loads(request.body)
        if not isinstance(data,dict):
            raise ValueError('Solicitud no válida.')
        result=registry_cloud.index_batch(str(data.get('ubigeo','')),str(data.get('after','')),data.get('lot_id') or None)
        return private(JsonResponse(result))
    except (ValueError,TypeError) as error:
        return private(JsonResponse({'error':str(error)},status=400))
    except (StorageError,sqlite3.DatabaseError):
        return private(JsonResponse({'error':'No se pudo actualizar la tabla. Reintenta el bloque; los documentos originales se conservan.'},status=503))


@require_GET
@admin_required
def asset(request, lot_id, filename):
    if not re.fullmatch(r'\d{14,18}',lot_id) or not re.fullmatch(r'[A-Za-z0-9_.-]+',filename):
        return private(JsonResponse({'error':'Archivo no válido.'},status=404))
    try:
        registry_cloud.validate_district(lot_id[:6])
        manifest,_=registry_cloud.read_manifest(lot_id[:6],lot_id)
        item=next((a for a in manifest.get('artifacts',[]) if a.get('filename')==filename),None)
        if not item or item.get('type') not in ('facade_image','cadastral_report_pdf','individual_record_pdf','cadastral_form_pdf'):
            return private(JsonResponse({'error':'El archivo no figura en el registro original.'},status=404))
        body,_=R2(timeout=12).get('geollaqta/'+lot_id[:6]+'/'+lot_id+'/'+filename)
        if not item.get('sha256') or hashlib.sha256(body).hexdigest()!=item['sha256']:
            raise ValueError('El archivo no coincide con su registro de integridad.')
        extension=filename.rsplit('.',1)[-1].lower()
        mime={'pdf':'application/pdf','jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png'}.get(extension)
        if not mime:
            raise ValueError('Formato no admitido.')
        response=private(HttpResponse(body,content_type=mime))
        response['X-Content-Type-Options']='nosniff'
        response['Content-Disposition']='inline; filename="'+filename+'"'
        return response
    except ValueError as error:
        return private(JsonResponse({'error':str(error)},status=422))
    except (StorageError, StopIteration):
        return private(JsonResponse({'error':'El original no está disponible en este momento.'},status=503))


@require_GET
@admin_required
def export(request):
    try:
        db,_=registry_cloud.load(request.GET.get('ubigeo','040126'))
        try:
            clause,values=registry.where(request.GET)
            output=io.StringIO(newline='')
            writer=csv.writer(output)
            def safe(value):
                value='' if value is None else str(value)
                return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
            kind=request.GET.get('table','records')
            if kind=='owners':
                writer.writerow(['Registro (FK)','Lote','Titular (FK)','Nombre del titular','Tipo de documento','Documento',
                                 'Porcentaje','Condición','Estado de identidad','PDF de origen','Página'])
                rows=db.execute('SELECT r.id,r.lot_id,o.id,o.name,o.document_type,o.document_number,ro.share,ro.condition,'
                                'o.identity_status,ro.filename,ro.page FROM records r JOIN record_owners ro ON ro.record_key=r.id '
                                'JOIN owners o ON o.id=ro.owner_id'+clause+' ORDER BY r.id,o.id',values)
                for row in rows:
                    data=list(row)
                    data[-2]=request.build_absolute_uri(registry.asset_url(row['lot_id'],row['filename']))
                    writer.writerow([safe(v) for v in data])
            else:
                dynamic=list(db.execute('SELECT DISTINCT field_key,label FROM fields ORDER BY label'))
                writer.writerow(['Registro',*registry.COLUMNS.values(),'Foto de fachada','PDF',*[r['label'] for r in dynamic]])
                for entry in db.execute('SELECT r.id,r.payload FROM records r'+clause+' ORDER BY r.lot_id,r.id',values):
                    data=json.loads(entry['payload'])
                    raw={}
                    for field in db.execute('SELECT field_key,value FROM fields WHERE record_key=?',(entry['id'],)):
                        if field['value'] is not None:
                            raw.setdefault(field['field_key'],[]).append(field['value'])
                    photo=request.build_absolute_uri(data['photo_urls'][0]) if data['photo_urls'] else ''
                    pdf=' | '.join(request.build_absolute_uri(item['url']) for item in data['pdf_urls'])
                    writer.writerow([safe(v) for v in [data['id'],*(data[k] for k in registry.COLUMNS),photo,pdf,
                                       *(' | '.join(dict.fromkeys(raw.get(r['field_key'],[]))) for r in dynamic)]])
        finally:
            db.close()
        response=private(HttpResponse('\ufeff'+output.getvalue(),content_type='text/csv; charset=utf-8'))
        response['Content-Disposition']='attachment; filename="catastro-'+('titulares' if kind=='owners' else 'registros')+'.csv"'
        return response
    except ValueError as error:
        return private(JsonResponse({'error':str(error)},status=400))
    except (StorageError,sqlite3.DatabaseError):
        return private(JsonResponse({'error':'No se pudo exportar el registro catastral.'},status=503))
