"""Deterministic, in-memory PDF path extraction; never assigns cadastral meaning."""
import hashlib
import json


MAX_PAGES = 100
MAX_DRAWINGS = 120_000
MAX_WORDS = 250_000


def _point(value):
    return [round(float(value.x), 5), round(float(value.y), 5)]


def _path_segments(items):
    segments = []
    current = []
    def flush():
        nonlocal current
        if len(current) > 1:
            segments.append(current)
        current = []
    for item in items:
        kind = item[0]
        if kind == 'l':
            a, b = item[1], item[2]
            if current and abs(current[-1].x-a.x)+abs(current[-1].y-a.y) > .02:
                flush()
            if not current: current.append(a)
            current.append(b)
        elif kind == 'c':
            a,b,c,d = item[1:5]
            if current and abs(current[-1].x-a.x)+abs(current[-1].y-a.y) > .02:
                flush()
            if not current: current.append(a)
            for i in range(1, 17):
                t=i/16;u=1-t
                current.append(type(a)(u**3*a.x+3*u*u*t*b.x+3*u*t*t*c.x+t**3*d.x,
                                       u**3*a.y+3*u*u*t*b.y+3*u*t*t*c.y+t**3*d.y))
        elif kind == 're':
            flush();r=item[1];segments.append([r.tl,r.tr,r.br,r.bl,r.tl])
        elif kind == 'qu':
            flush();q=item[1];segments.append([q.ul,q.ur,q.lr,q.ll,q.ul])
        else:
            flush()
    flush()
    return segments


def extract(body):
    if not body.startswith(b'%PDF-') or len(body)>12*1024*1024:
        raise ValueError('Se requiere el PDF registrado de hasta 12 MB.')
    import fitz
    try:
        with fitz.open(stream=body,filetype='pdf') as document:
            if document.needs_pass or not 1<=len(document)<=MAX_PAGES:
                raise ValueError('El PDF está protegido o supera 100 páginas.')
            features=[];page_report=[];draw_count=word_count=0
            for page_number,page in enumerate(document,1):
                drawings=page.get_drawings();draw_count+=len(drawings)
                words=page.get_text('words');word_count+=len(words)
                if draw_count>MAX_DRAWINGS or word_count>MAX_WORDS:
                    raise ValueError('El plano supera los límites de extracción de esta instancia; divídelo por sectores.')
                page_paths=0
                for index,drawing in enumerate(drawings):
                    paths=_path_segments(drawing.get('items',()))
                    if not paths:continue
                    coords=[[_point(p) for p in path] for path in paths]
                    # Closed/fill paths are still source drawing primitives;
                    # they do not establish cadastral parcel boundaries.
                    if len(coords)==1:
                        geometry={'type':'LineString','coordinates':coords[0]}
                    else:
                        geometry={'type':'MultiLineString','coordinates':coords}
                    color=drawing.get('color');fill=drawing.get('fill')
                    props={'page':page_number,'drawing_index':index,'source_layer':str(drawing.get('layer') or ''),
                           'source_type':'filled_path' if drawing.get('fill') else 'vector_path',
                           'stroke_rgb':list(color) if color else None,'fill_rgb':list(fill) if fill else None,
                           'line_width_pdf_points':float(drawing.get('width') or 0),
                           'coordinate_space':'PDF_PAGE_POINTS','georeferenced':False}
                    features.append({'type':'Feature','id':f'p{page_number}-d{index}','geometry':geometry,'properties':props})
                    page_paths+=1
                for index,word in enumerate(words):
                    x0,y0,x1,y1,text,*rest=word
                    features.append({'type':'Feature','id':f'p{page_number}-t{index}',
                        'geometry':{'type':'Point','coordinates':[round((x0+x1)/2,5),round((y0+y1)/2,5)]},
                        'properties':{'page':page_number,'source_type':'pdf_text','text':str(text)[:500],
                          'bbox_pdf_points':[round(x0,4),round(y0,4),round(x1,4),round(y1,4)],
                          'coordinate_space':'PDF_PAGE_POINTS','georeferenced':False}})
                page_report.append({'page':page_number,'width_pdf_points':round(page.rect.width,3),
                    'height_pdf_points':round(page.rect.height,3),'rotation':page.rotation,
                    'vector_paths':page_paths,'text_words':len(words)})
            payload={'type':'FeatureCollection','features':features,'metadata':{
                'extractor':'prometeo-pdf-vector-v1','original_sha256':hashlib.sha256(body).hexdigest(),
                'pages':page_report,'vector_paths':draw_count,'text_words':word_count,
                'coordinate_space':'LOCAL_PDF_PAGE_POINTS','georeferenced':False,
                'limitations':['La extracción conserva trazos y texto del PDF; no identifica lotes, manzanas, frentes ni cotas semánticamente.',
                  'Las coordenadas siguen en puntos locales de página; no se inventa EPSG ni ubicación geográfica.',
                  'Los PDF escaneados no producen trazos vectoriales. El OCR es una etapa posterior y debe revisarse.']}}
            serialized=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
            return payload,serialized
    except fitz.FileDataError:
        raise ValueError('No se pudo leer el PDF.') from None


def stage(version_id, actor):
    from . import source_manager
    from .storage import R2
    original=source_manager.version_payload(version_id)
    body=source_manager.pdf(version_id) if original else None
    if body is None:raise ValueError('El original de esta versión no está disponible.')
    source=original['source'];parent=original['version']
    if not parent.get('original',{}).get('sha256') or hashlib.sha256(body).hexdigest()!=parent['original']['sha256']:
        raise ValueError('La huella del PDF no coincide con la versión registrada.')
    data,serialized=extract(body)
    if len(serialized)>19_000_000:
        raise ValueError('El GeoJSON excede el límite de archivo derivado; procesa el PDF por partes.')
    digest=hashlib.sha256(serialized).hexdigest();name='vectores.geojson'
    key=f"geollaqta/maestro/derivados/{parent['original']['sha256']}/{digest}/{name}"
    R2().put_verified(key,serialized,'application/geo+json')
    manifest={name:{'sha256':digest,'size':len(serialized),'content_type':'application/geo+json','object_key':key}}
    version={'id':'vector-pdf:'+digest[:40],'label':'Vectorización automática · '+digest[:10],
      'source_date':parent.get('source_date'),'crs':'LOCAL_PDF_PAGE_POINTS',
      'georeferencing':{'status':'pending'},'original':dict(parent['original']),
      'parent_version_id':version_id,'vector_artifacts':manifest,
      'vector_review':{'status':'pending_review','extractor':'prometeo-pdf-vector-v1',
        'candidate_faces':0,
        'vector_paths':data['metadata']['vector_paths'],'text_words':data['metadata']['text_words'],
        'geojson_sha256':digest,'coordinate_space':'LOCAL_PDF_PAGE_POINTS','georeferenced':False,
        'notes':data['metadata']['limitations']}}
    payload={'source':dict(source),'version':version,'features':[]}
    result=source_manager.store().stage(payload,source_manager.store().revision,actor)
    return {**result,'version_id':version['id'],'review':version['vector_review']}
