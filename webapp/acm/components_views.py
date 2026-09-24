"""Dashboard ACM por componentes: consultas en vivo sin modificar los anuncios."""
import json
import logging
import math
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.core import signing
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .components_engine import candidates, calculate, parameters, positive, number, SOURCES

logger = logging.getLogger(__name__)
SALT = 'acm-componentes-v1'


def session_user(request):
    for user in (getattr(request,'current_user',None),getattr(request,'user',None)):
        if user and getattr(user,'is_active',False) and getattr(user,'is_authenticated',False):
            return user
    return None


def authenticated(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not session_user(request):
            return JsonResponse({'error':'Tu sesión expiró. Inicia sesión de nuevo.'},status=401)
        response=view(request,*args,**kwargs)
        response['Cache-Control']='no-store'
        return response
    return wrapped


def user_key(request):
    user=session_user(request)
    return f'{user._meta.label_lower}:{user.pk}' if hasattr(user,'_meta') else str(user.pk)


@ensure_csrf_cookie
def page(request):
    # The page shell exposes no records and retains the site's login dialog.
    # Both data endpoints still require an authenticated, active session.
    response = render(request,'acm/components.html',{
        'sources':SOURCES,
        'test_mode':'analisis-pruebas' in request.path,
        'google_maps_api_key':getattr(settings,'GOOGLE_MAPS_API_KEY',None) or 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',
    })
    response['Cache-Control'] = 'no-store'
    response['X-ACM-Model'] = 'componentes-1'
    return response


def clean_link(value):
    value=str(value or '')
    return value if value.startswith(('https://','http://')) else ''


def scraped_rows(p):
    from ingestas.models import PropiedadesCompetencia
    from cuadrantizacion.views import _map_image_url
    lat_delta=p['max_radius']/110000
    lng_delta=lat_delta/max(.01,math.cos(math.radians(p['lat'])))
    query=PropiedadesCompetencia.objects.filter(
        fuente__in=[s for s in p['sources'] if s!='propify'],
        latitud__gte=p['lat']-lat_delta,latitud__lte=p['lat']+lat_delta,
        longitud__gte=p['lng']-lng_delta,longitud__lte=p['lng']+lng_delta,
    ).exclude(estado_publicacion='retirada').exclude(tipo_operacion='Alquiler')
    # Optional quality module may be installed independently; no new schema dependency.
    try:
        review=apps.get_model('ingestas','RevisionPropiedadScraping')
    except LookupError:
        review=None
    excluded=set(review.objects.filter(excluida=True).values_list('propiedad_id',flat=True)) if review else set()
    for row in query.values('id','fuente','id_origen','titulo','tipo_inmueble','tipo_operacion',
            'precio_usd','precio_soles','area_terreno','area_construida','latitud','longitud',
            'precision_ubicacion','estado_publicacion','distrito','url','imagen_url','descripcion','dormitorios','banos').iterator(chunk_size=500):
        usd=positive(row['precio_usd']);pen=positive(row['precio_soles'])
        yield {'id':f"{row['fuente']}-{row['id']}",'record_id':row['id'],
            'source':row['fuente'],'code':row['id_origen'],
            'title':row['titulo'] or row['id_origen'],'kind':row['tipo_inmueble'],
            'description':row['descripcion'] or '',
            'rooms':row['dormitorios'],'baths':row['banos'],'floor':None,
            'price':usd or (pen/3.44 if pen else None),'converted':not bool(usd) and bool(pen),
            'land':positive(row['area_terreno']),'built':positive(row['area_construida']),
            'lat':float(row['latitud']),'lng':float(row['longitud']),
            'precision':row['precision_ubicacion'],'state':row['estado_publicacion'],
            'operation':row['tipo_operacion'],'district':row['distrito'],
            'url':clean_link(row['url']),'image':clean_link(_map_image_url(row['imagen_url'])),
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
            'baths':(number(row.get('bathrooms')) or 0)+(number(row.get('half_bathrooms')) or 0)*.5 if row.get('bathrooms') is not None else None,
            # unit_location is not a verified floor number; do not guess it.
            'floor':None,
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
        try: records.extend(propify_rows())
        except Exception:
            logger.exception('ACM componentes: no se pudo consultar Propify')
            warnings.append('Propify no respondió: resultado parcial. Repite la búsqueda para incluirlo.')
    return candidates(records,p),warnings


@require_POST
@csrf_protect
@authenticated
def search(request):
    try:
        p=parameters(json.loads(request.body))
    except (ValueError,TypeError,AttributeError):
        return JsonResponse({'error':'Revisa ubicación, áreas, radios y fuentes seleccionadas.'},status=400)
    try:
        records,warnings=load_records(p)
        if len(records)>4000:
            return JsonResponse({'error':'Hay demasiados registros. Reduce el área de búsqueda.'},status=400)
        token=signing.dumps({'user':user_key(request),'params':p,'records':records,'warnings':warnings},salt=SALT,compress=True)
        logger.info('ACM componentes: búsqueda fuentes=%s radio=%s registros=%s parcial=%s',p['sources'],p['radius'],len(records),bool(warnings))
        return JsonResponse({'params':p,'records':records,'warnings':warnings,'token':token,'result':calculate(records,p)})
    except Exception:
        logger.exception('ACM componentes: error de búsqueda')
        return JsonResponse({'error':'No se pudo consultar los comparables. Reintenta; el error quedó registrado.'},status=503)


@require_POST
@csrf_protect
@authenticated
def recalculate(request):
    try:
        data=json.loads(request.body)
        state=signing.loads(data.get('token',''),salt=SALT,max_age=1800)
        if state['user']!=user_key(request):raise signing.BadSignature('session mismatch')
        excluded=data.get('excluded',[])
        ids={r['id'] for r in state['records']}
        if not isinstance(excluded,list) or len(excluded)>4000 or any(not isinstance(i,str) or i not in ids for i in excluded):
            raise ValueError('selection')
        return JsonResponse({'result':calculate(state['records'],state['params'],excluded)})
    except signing.SignatureExpired:
        return JsonResponse({'error':'La búsqueda venció (30 minutos). Busca nuevamente para actualizar los datos.'},status=409)
    except (signing.BadSignature,ValueError,TypeError,KeyError,AttributeError):
        return JsonResponse({'error':'Búsqueda o selección inválida. Busca nuevamente.'},status=400)
