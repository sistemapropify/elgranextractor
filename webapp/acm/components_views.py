"""Dashboard ACM por componentes: consultas en vivo sin modificar los anuncios."""
import json
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as SourceTimeout
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.core import signing
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from map_config import google_maps_api_key
from .access import required, template_context
from .access_data import issue_snapshot, read_snapshot, project, restore_selection

from .components_engine import candidates, calculate, parameters, positive, number, SOURCES

logger = logging.getLogger(__name__)
SALT = 'acm-componentes-v1'
_propify_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='acm-propify')
_propify_lock = threading.Lock()
_propify_pending = None


def bounded_propify_rows():
    """A slow external source must not consume the entire browser deadline."""
    from django.db import connections
    def read():
        try:
            return list(propify_rows())
        finally:
            connections.close_all()
    global _propify_pending
    with _propify_lock:
        if _propify_pending is None or _propify_pending.done():
            _propify_pending = _propify_executor.submit(read)
        future = _propify_pending
    # Concurrent requests share one outstanding read, so timeouts cannot create
    # an unbounded number of SQL connections or worker threads.
    return future.result(timeout=8)


def session_user(request):
    return getattr(request, 'acm_identity', None)


def authenticated(view):
    capabilities = {'search': 'calculate', 'recalculate': 'calculate', 'explain_ai': 'ai',
                    'word_report': 'reports', 'pdf_report': 'reports', 'html_report': 'reports',
                    'save_history': 'history', 'replicate_history': 'history',
                    'history_word_report': 'reports', 'history_pdf_report': 'reports'}
    @wraps(view)
    def checked(request, *args, **kwargs):
        if view.__name__ in ('history_word_report','history_pdf_report') and not request.acm_access.permissions['history']:
            return JsonResponse({'error':'El historial no está habilitado.'}, status=403)
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
            except (ValueError, TypeError):
                data = {}
            permissions = request.acm_access.permissions
            if isinstance(data, dict):
                if data.get('manual_valuation') is not None and not permissions['adjust_valuation']:
                    return JsonResponse({'error': 'El ajuste de valoración no está habilitado.'}, status=403)
                if data.get('report_notes') and not permissions['report_notes']:
                    return JsonResponse({'error': 'Las observaciones del reporte no están habilitadas.'}, status=403)
                if data.get('target_areas') is not None and not permissions['adjust_areas']:
                    return JsonResponse({'error': 'El ajuste de superficies no está habilitado.'}, status=403)
        return view(request, *args, **kwargs)
    return required(capabilities.get(view.__name__))(checked)


def user_key(request):
    user=session_user(request)
    return f'{user._meta.label_lower}:{user.pk}' if hasattr(user,'_meta') else str(user.pk)


@ensure_csrf_cookie
@required(page=True)
def page(request, replication=None):
    # The page shell exposes no records and retains the site's login dialog.
    # Both data endpoints still require an authenticated, active session.
    # Capa de zonificación (misma que cuadrantización): si algo falla, la página
    # del ACM debe seguir funcionando sin el plano superpuesto.
    try:
        from cuadrantizacion.map_layers import map_layers_config
        config_capas = map_layers_config(include_zones=True) if request.acm_access.permissions['pdm_polygons'] else {'raster': [], 'vectoriales': [], 'zonas': []}
    except Exception:
        logger.warning('No se pudo cargar la capa de zonificación para el ACM', exc_info=True)
        config_capas = {'raster': [], 'vectoriales': [], 'zonas': []}

    from .role_analysis import resume_analysis
    response = render(request,'acm/components.html',{
        'analysis_resume': resume_analysis(request),
        'sources':SOURCES,
        'replication': replication,
        'acm_is_authenticated': session_user(request) is not None,
        'test_mode':'analisis-pruebas' in request.path,
        'google_maps_api_key':google_maps_api_key(),
        'capas_raster':config_capas['raster'],
        'capas_vectoriales':config_capas['vectoriales'],
        'zonas_mapa':config_capas['zonas'],
        **template_context(request),
    })
    response['Cache-Control'] = 'no-store'
    from .components_engine import VERSION
    response['X-ACM-Model'] = VERSION
    return response


@require_GET
@authenticated
def replicate_history(request, uuid):
    from .access_models import ACMPortalAnalysis
    from .access import database
    history = get_object_or_404(ACMPortalAnalysis.objects.using(database()), id=uuid, owner_id=session_user(request).pk)
    try:
        params = parameters(history.snapshot['params'])
    except (ValueError, TypeError, KeyError):
        params = None
    if params is None:
        return HttpResponse('Este ACM antiguo no guardó los datos completos de la propiedad objetivo. '
                            'Crea un nuevo análisis indicando su ubicación y metraje.', status=409)
    safe, _, _ = project(request, {'params': params})
    return page(request, replication={'code': history.codigo_display, 'params': safe['params']})


def clean_link(value):
    value=str(value or '')
    return value if value.startswith(('https://','http://')) else ''


def scraped_rows(p):
    from ingestas.models import PropiedadesCompetencia
    from cuadrantizacion.views import _map_image_url
    from scrapi.photo_gallery import gallery_photos
    lat_delta=p['max_radius']/110000
    lng_delta=lat_delta/max(.01,math.cos(math.radians(p['lat'])))
    query=PropiedadesCompetencia.objects.filter(
        fuente__in=[s for s in p['sources'] if s!='propify'],
        latitud__gte=p['lat']-lat_delta,latitud__lte=p['lat']+lat_delta,
        longitud__gte=p['lng']-lng_delta,longitud__lte=p['lng']+lng_delta,
    ).exclude(tipo_operacion='Alquiler').annotate(
        original_listing_title=F('datos_crudos__Titulo'),
        original_listing_title_lower=F('datos_crudos__titulo'),
        age_conflict=F('datos_crudos___age_evidence__reason'))
    # Optional quality module may be installed independently; no new schema dependency.
    try:
        review=apps.get_model('ingestas','RevisionPropiedadScraping')
    except LookupError:
        review=None
    excluded=set(); confirmed_age=set()
    if review:
        for revision in review.objects.values('propiedad_id','excluida','correcta','campos_protegidos').iterator(chunk_size=500):
            if revision['excluida']:
                excluded.add(revision['propiedad_id'])
            if revision['correcta'] or 'antiguedad_anios' in (revision['campos_protegidos'] or []):
                confirmed_age.add(revision['propiedad_id'])
    for row in query.values('id','fuente','id_origen','titulo','tipo_inmueble','tipo_operacion','original_listing_title','original_listing_title_lower',
            'precio_usd','precio_soles','area_terreno','area_construida','latitud','longitud',
            'precision_ubicacion','estado_publicacion','primera_vez_vista','ultima_vez_vista',
            'fecha_primera_ausencia','fecha_retiro_confirmado','ausencias_consecutivas',
            'distrito','url','imagen_url','descripcion','dormitorios','banos','antiguedad_anios','age_conflict',
            'estacionamientos','amenities','datos_crudos').iterator(chunk_size=500):
        usd=positive(row['precio_usd']);pen=positive(row['precio_soles'])
        # Reuse the same verified/legacy feature readers as the quality editor.
        # Raw source evidence stays on the server; only compact values are emitted.
        feature_record = PropiedadesCompetencia(tipo_inmueble=row['tipo_inmueble'],
            descripcion=row['descripcion'], titulo=row['titulo'], estacionamientos=row['estacionamientos'],
            amenities=row['amenities'], datos_crudos=row['datos_crudos'])
        parking = feature_record.building_features['parking']
        floor_label = feature_record.piso_departamento
        lifecycle_state = row['estado_publicacion'] or 'sin_verificar'
        cover = row['imagen_url']
        if not cover:
            photos = gallery_photos(row['datos_crudos'])
            cover = photos[0]['url'] if photos else None
        yield {'id':f"{row['fuente']}-{row['id']}",'record_id':row['id'],
            'source':row['fuente'],'code':row['id_origen'],
            'title':row['titulo'] or row['id_origen'],'kind':row['tipo_inmueble'],
            'description':row['descripcion'] or '',
            'rooms':row['dormitorios'],'baths':row['banos'],
            'floor':int(floor_label) if floor_label is not None and str(floor_label).isdigit() else None,
            'floor_label':floor_label, 'parking_has':parking['has'],
            'parking_types':parking.get('types'), 'parking_status':parking['status'],
            'age':number(row['antiguedad_anios']),
            'age_conflict':None if row['id'] in confirmed_age else row['age_conflict'],
            'price':usd or (pen/3.44 if pen else None),'converted':not bool(usd) and bool(pen),
            'land':positive(row['area_terreno']),'built':positive(row['area_construida']),
            'lat':float(row['latitud']),'lng':float(row['longitud']),
            'precision':row['precision_ubicacion'],'state':lifecycle_state,
            'first_seen':row['primera_vez_vista'].isoformat() if row['primera_vez_vista'] else None,
            'last_seen':row['ultima_vez_vista'].isoformat() if row['ultima_vez_vista'] else None,
            'first_missing':row['fecha_primera_ausencia'].isoformat() if row['fecha_primera_ausencia'] else None,
            'retired_at':row['fecha_retiro_confirmado'].isoformat() if row['fecha_retiro_confirmado'] else None,
            'consecutive_absences':row['ausencias_consecutivas'] or 0,
            'operation':row['tipo_operacion'],'district':row['distrito'],
            '_operation_title':row['original_listing_title'],
            '_operation_title_lower':row['original_listing_title_lower'],
            'url':clean_link(row['url']),'image':clean_link(_map_image_url(cover)),
            'review_excluded':row['id'] in excluded}


def propify_rows():
    # Reuse the available-only loader; never fabricate coordinates from district centers.
    from cuadrantizacion.views import _available_propify_properties
    for row in _available_propify_properties():
        if row['operation_type']=='Alquiler':continue
        price=positive(row['price'])
        converted=row['currency_symbol']!='$'
        yield {'id':f"propify-{row['id']}",'record_id':None,
            'source':'propify','code':row['code'],
            'title':row['title'],'kind':row['property_type'],
            'rooms':number(row.get('bedrooms')),
            'age':number(row.get('antiquity_years')),
            'baths':(number(row.get('bathrooms')) or 0)+(number(row.get('half_bathrooms')) or 0)*.5 if row.get('bathrooms') is not None else None,
            # unit_location is not a verified floor number; do not guess it.
            'floor':None, 'floor_label':None, 'parking_has':None,
            'parking_types':None, 'parking_status':'unknown',
            'price':price/3.44 if price and converted else price,'converted':converted,
            'land':positive(row['land_area_m2']),'built':positive(row['built_area_m2']),
            'lat':row['lat'],'lng':row['lng'],'precision':'exacta','state':'activa',
            'operation':row['operation_type'],'district':row['district'],
            'url':clean_link(row.get('url')) or ('https://propifai.com/propiedad/'+str(row['code']) if row.get('code') else ''),
            'image':clean_link(row.get('image_url')),'review_excluded':False}


def load_records(p):
    records=[];warnings=[]
    if any(s!='propify' for s in p['sources']):
        # Failure must be explicit: do not label an incomplete portal query as a full analysis.
        records.extend(scraped_rows(p))
    if 'propify' in p['sources']:
        try: records.extend(bounded_propify_rows())
        except SourceTimeout:
            logger.warning('ACM componentes: Propify superó el plazo de consulta')
            warnings.append('Propify no respondió a tiempo: resultado parcial con los portales disponibles. Repite la búsqueda para incluirlo.')
        except Exception:
            logger.exception('ACM componentes: no se pudo consultar Propify')
            warnings.append('Propify no respondió: resultado parcial. Repite la búsqueda para incluirlo.')
    return candidates(records,p),warnings


@require_POST
@csrf_protect
@authenticated
def search(request):
    try:
        payload=json.loads(request.body)
        payload['sources']=list(SOURCES)
        p=parameters(payload)
    except (ValueError,TypeError,AttributeError):
        return JsonResponse({'error':'Revisa ubicación, áreas, radios y fuentes seleccionadas.'},status=400)
    try:
        records,warnings=load_records(p)
        if len(records)>4000:
            return JsonResponse({'error':'Hay demasiados registros. Reduce el área de búsqueda.'},status=400)
        state={'user':user_key(request),'params':p,'records':records,'warnings':warnings}
        token=issue_snapshot(request,state)
        logger.info('ACM componentes: búsqueda fuentes=%s radio=%s registros=%s parcial=%s',p['sources'],p['radius'],len(records),bool(warnings))
        client,result,_=project(request,state,calculate(records,p))
        return JsonResponse({**client,'token':token,'result':result})
    except Exception:
        logger.exception('ACM componentes: error de búsqueda')
        return JsonResponse({'error':'No se pudo consultar los comparables. Reintenta; el error quedó registrado.'},status=503)


@require_POST
@csrf_protect
@authenticated
def recalculate(request):
    try:
        state,excluded=_signed_selection(request)
        client,result,_=project(request,state,calculate(state['records'],state['params'],excluded))
        return JsonResponse({'result':result,'params':client['params']})
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció (30 minutos). Busca nuevamente para actualizar los datos.'},status=409)
    except (signing.BadSignature,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida. Busca nuevamente.'},status=400)


def _signed_selection(request, data=None):
    if data is None:
        data=json.loads(request.body)
    state=read_snapshot(request,data.get('token',''))
    data=restore_selection(request,state,data)
    if state['user']!=user_key(request):raise signing.BadSignature('session mismatch')
    excluded=data.get('excluded',[])
    ids={r['id'] for r in state['records']}
    if not isinstance(excluded,list) or len(excluded)>4000 or any(not isinstance(i,str) or i not in ids for i in excluded):
        raise ValueError('selection')
    if 'report_ids' in data:
        selected=data['report_ids']
        if not isinstance(selected,list) or len(selected)>4000 or any(not isinstance(i,str) or i not in ids for i in selected):
            raise ValueError('report selection')
        state['params']['report_ids']=list(dict.fromkeys(selected))
    if 'manual_valuation' in data:
        if data['manual_valuation'] is None:
            state['params'].pop('manual_valuation', None)
        else:
            total=number(data['manual_valuation'])
            if isinstance(data['manual_valuation'], bool) or total is None or not 0<=total<=1000000000:
                raise ValueError('manual valuation')
            state['params']['manual_valuation']=round(total,2)
    if 'report_notes' in data:
        notes=data['report_notes']
        if not isinstance(notes,str) or len(notes)>10000 or any(ord(c)<32 and c not in '\r\n\t' for c in notes):
            raise ValueError('Justificación u observaciones: usa texto de hasta 10.000 caracteres.')
        notes=notes.replace('\r\n','\n').replace('\r','\n').strip()
        if notes:
            state['params']['report_notes']=notes
        else:
            state['params'].pop('report_notes', None)
    target=data.get('target_areas')
    if target is not None:
        if state['params'].get('property_type','Casa')!='Casa' or not isinstance(target,dict):
            raise ValueError('scenario')
        p=state['params']
        p['weight_reference']={key:p[key] for key in ('land','built','radius')}
        for key in ('land','built'):
            area=positive(target.get(key))
            if area is None or area>1000000:raise ValueError('scenario areas')
            p[key]=area
    return state,excluded


def _persist_history(user, params, records, result, excluded):
    from .access_data import persist_history
    return persist_history(user,params,records,result,excluded)


@require_POST
@csrf_protect
@authenticated
def explain_ai(request):
    try:
        state,excluded=_signed_selection(request)
        result=calculate(state['records'],state['params'],excluded)
        if not state['records']:
            return JsonResponse({'error':'Primero busca propiedades para analizar.'},status=400)
        from .components_ai import explain_result, propose_result, ExplanationBusy
        client,client_result,client_excluded=project(request,state,result,excluded)
        original_ids={row['id']:original['id'] for row,original in zip(client['records'],state['records'])}
        try:
            if result['model'] in ('components','built','land'):
                proposal=propose_result(user_key(request),client['params'],client['records'],client_result,client_excluded,client.get('warnings',[]))
                current_params={**state['params'],'ai_review_recommendations':proposal.get('reviews',[])}
                proposed_params={**state['params'],'reference_ids':[original_ids[i] for i in proposal['ids']],
                                 'proposal_explanation':proposal['explanation'],
                                 'ai_review_recommendations':proposal.get('reviews',[])}
                proposed_result=calculate(state['records'],proposed_params,excluded) if proposal['ids'] else result
                new_state={**state,'params':proposed_params}
                token=issue_snapshot(request,new_state)
                safe,new_result,_=project(request,new_state,proposed_result)
                current_token=issue_snapshot(request,{**state,'params':current_params})
                safe_current,_,_=project(request,{**state,'params':current_params})
                by_id={row['id']:row for row in client['records']}
                return JsonResponse({'explanation':proposal['explanation'],'total':(result.get('new') or {}).get('total'),
                    'current_token':current_token,'current_params':safe_current['params'],
                    'proposal':{'ids':proposal['ids'],'token':token,'params':safe['params'],
                        'result':new_result,'omitted':proposal['omitted'],'reviews':proposal.get('reviews',[]),
                        'labels':[by_id[i]['source'].upper()+' · '+by_id[i]['code'] for i in proposal['ids']]}})
            text=explain_result(user_key(request),client['params'],client['records'],client_result,client_excluded,client.get('warnings',[]))
        except ExplanationBusy:
            return JsonResponse({'error':'Hay una explicación en curso. Espera antes de reintentar.'},status=429)
        return JsonResponse({'explanation':text,'total':result['new']['total']})
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció. Busca nuevamente.'},status=409)
    except (signing.BadSignature,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida.'},status=400)
    except Exception:
        logger.exception('ACM: no se pudo generar explicación IA')
        return JsonResponse({'error':'La IA no pudo responder. Tu cálculo se conserva; puedes reintentar.'},status=503)


@require_POST
@csrf_protect
@authenticated
def word_report(request):
    try:
        state,excluded=_signed_selection(request)
        if state['params'].get('report_ids')==[]:
            return JsonResponse({'error':'Marca al menos una propiedad para incluirla en el informe.'},status=422)
        result=calculate(state['records'],state['params'],excluded)
        history,_=_persist_history(session_user(request),state['params'],state['records'],result,excluded)
        from .components_report import build_acm_docx
        safe,visible_result,visible_excluded=project(request,state,result,excluded,report=True)
        content=build_acm_docx(safe['params'],safe['records'],visible_result,visible_excluded,user=session_user(request))
        response=HttpResponse(content,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition']='attachment; filename="informe-acm.docx"'
        response['X-ACM-History-Code']=history.codigo_display
        response['Cache-Control']='no-store'
        return response
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció (30 minutos). Busca nuevamente para descargar el informe.'},status=409)
    except (signing.BadSignature,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida. Busca nuevamente.'},status=400)
    except Exception:
        logger.exception('ACM componentes: no se pudo generar el informe Word')
        return JsonResponse({'error':'No se pudo generar el informe Word. El error quedó registrado.'},status=503)


@require_POST
@csrf_protect
@authenticated
def pdf_report(request):
    """Informe PDF con la estructura del ACM de Propify (solo identidad Propify)."""
    try:
        state,excluded=_signed_selection(request)
        if state['params'].get('report_ids')==[]:
            return JsonResponse({'error':'Marca al menos una propiedad para incluirla en el informe.'},status=422)
        result=calculate(state['records'],state['params'],excluded)
        history,_=_persist_history(session_user(request),state['params'],state['records'],result,excluded)
        from .components_pdf import build_acm_pdf
        safe,visible_result,visible_excluded=project(request,state,result,excluded,report=True)
        content=build_acm_pdf(safe['params'],safe['records'],visible_result,visible_excluded,user=session_user(request))
        response=HttpResponse(content,content_type='application/pdf')
        response['Content-Disposition']='attachment; filename="informe-acm.pdf"'
        response['X-ACM-History-Code']=history.codigo_display
        response['Cache-Control']='no-store'
        return response
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció (30 minutos). Busca nuevamente para descargar el informe.'},status=409)
    except (signing.BadSignature,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida. Busca nuevamente.'},status=400)
    except Exception:
        logger.exception('ACM componentes: no se pudo generar el informe PDF')
        return JsonResponse({'error':'No se pudo generar el informe PDF. El error quedó registrado.'},status=503)


@require_POST
@csrf_protect
@authenticated
def html_report(request):
    try:
        state,excluded=_signed_selection(request)
        if state['params'].get('report_ids')==[]:
            return JsonResponse({'error':'Marca al menos una propiedad para incluirla en el informe.'},status=422)
        result=calculate(state['records'],state['params'],excluded)
        if not result.get('new'):
            return JsonResponse({'error':'Primero completa un cálculo ACM.'},status=422)
        from .components_html import build_acm_html
        safe,visible_result,visible_excluded=project(request,state,result,excluded,report=True)
        content=build_acm_html(safe['params'],safe['records'],visible_result,visible_excluded)
        history,_=_persist_history(session_user(request),state['params'],state['records'],result,excluded)
        response=HttpResponse(content,content_type='text/html; charset=utf-8')
        response['Content-Disposition']='attachment; filename="informe-acm.html"'
        response['X-ACM-History-Code']=history.codigo_display
        response['Cache-Control']='no-store'
        return response
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció (30 minutos). Busca nuevamente para descargar el informe.'},status=409)
    except (signing.BadSignature,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida. Busca nuevamente.'},status=400)
    except Exception:
        logger.exception('ACM componentes: no se pudo generar el informe HTML')
        return JsonResponse({'error':'No se pudo generar el informe HTML. El error quedó registrado.'},status=503)


@require_POST
@csrf_protect
@authenticated
def save_history(request):
    try:
        state,excluded=_signed_selection(request)
        if state['params'].get('report_ids')==[]:
            return JsonResponse({'error':'Marca al menos una propiedad para incluirla en el informe.'},status=422)
        result=calculate(state['records'],state['params'],excluded)
        history,created=_persist_history(session_user(request),state['params'],state['records'],result,excluded)
        return JsonResponse({'status':'ok','created':created,'id':str(history.id),'code':history.codigo_display})
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció (30 minutos). Busca nuevamente para guardarla.'},status=409)
    except ValueError as exc:
        return JsonResponse({'error':str(exc)},status=422)
    except (signing.BadSignature,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida. Busca nuevamente.'},status=400)
    except Exception:
        logger.exception('ACM componentes: no se pudo guardar en el historial')
        return JsonResponse({'error':'No se pudo guardar el análisis. El error quedó registrado.'},status=503)


@authenticated
def history_word_report(request, uuid):
    return _history_report(request, uuid, 'word')


@authenticated
def history_pdf_report(request, uuid):
    return _history_report(request, uuid, 'pdf')


def _history_report(request, uuid, kind):
    from .access_models import ACMPortalAnalysis
    from .access import database
    row=get_object_or_404(ACMPortalAnalysis.objects.using(database()), id=uuid, owner_id=session_user(request).pk)
    snapshot=row.snapshot
    safe,result,excluded=project(request,snapshot,snapshot['result'],snapshot.get('excluded',()),report=True)
    if kind=='word':
        from .components_report import build_acm_docx
        content=build_acm_docx(safe['params'],safe['records'],result,excluded,generated_at=row.created_at,user=session_user(request))
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        extension='docx'
    else:
        from .components_pdf import build_acm_pdf
        content=build_acm_pdf(safe['params'],safe['records'],result,excluded,generated_at=row.created_at,user=session_user(request))
        mime='application/pdf';extension='pdf'
    response=HttpResponse(content,content_type=mime)
    response['Content-Disposition']=f'attachment; filename="{row.codigo_display}.{extension}"'
    return response
