"""Archive reviewed conversion outputs; never migrate or activate property rows."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .master_store import encoded
from .storage import R2, StorageError

MIMES={'.html':'text/html; charset=utf-8','.csv':'text/csv; charset=utf-8',
       '.json':'application/json','.geojson':'application/geo+json','.svg':'image/svg+xml','.dxf':'application/dxf',
       '.zip':'application/zip','.md':'text/plain; charset=utf-8'}


def archive(directory, original_version_id, actor):
    """Explicit operator action for this PDF's derived files; originals stay intact."""
    from . import source_manager
    if not source_manager.durable():
        raise ValueError('El archivo de derivados requiere la conexión privada D1/R2.')
    root=Path(directory)
    data=json.loads((root/'sector32.capas.json').read_text(encoding='utf8'))
    original=source_manager.version_payload(original_version_id)
    if not original or data['source']['sha256']!=original['version']['original']['sha256']:
        raise ValueError('Los vectores no corresponden al PDF original de esta versión.')
    files=sorted(p for p in root.iterdir() if p.is_file() and p.suffix in MIMES)
    if not files or len(files)>40:
        raise ValueError('Paquete de derivados no válido.')
    manifest={}
    for path in files:
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',path.name):
            raise ValueError('Nombre de derivado no válido.')
        body=path.read_bytes()
        if not 0<len(body)<=19_000_000:
            raise ValueError('El derivado supera el tamaño admitido: '+path.name)
        manifest[path.name]={'sha256':hashlib.sha256(body).hexdigest(),'size':len(body),'content_type':MIMES[path.suffix]}
    package_sha=hashlib.sha256(encoded(manifest).encode()).hexdigest()
    prefix='geollaqta/maestro/derivados/'+data['source']['sha256']+'/'+package_sha+'/'
    vid='vectores:'+package_sha[:40]
    storage=R2()
    for filename,item in manifest.items():
        item['object_key']=prefix+filename
        storage.put_verified(item['object_key'],(root/filename).read_bytes(),item['content_type'])
    review={'candidate_faces':len(data['lots']),'candidate_corners':sum(r['es_esquina'] is True for r in data['lots']),
            'sides_with_dimensions':sum(r['longitud_lado_propuesta'] is not None for r in data['sides']),
            'source_block_codes_read':sum(bool(l['texto_propuesto']) for l in data['labels']['codigos_manzana']),
            'faces_with_lot_number':sum(r['numero_lote_propuesto'] is not None for r in data['lots']),
            'qa':data['qa'],'notes':data['notes'],'status':'pending_review','package_sha256':package_sha}
    payload={'source':deepcopy(original['source']),'version':{'id':vid,'label':'Capas vectoriales · '+package_sha[:10],
        'source_date':original['version'].get('source_date'),'crs':'LOCAL_PDF_DISPLAY_POINTS',
        'georeferencing':{'status':'pending'},'original':deepcopy(original['version']['original']),
        'parent_version_id':original_version_id,'vector_review':review,'vector_artifacts':manifest},'features':[]}
    store=source_manager.store()
    return {**store.stage(payload,store.revision,actor),'version_id':vid,'review':review}


def retrieve(version_id,filename):
    from . import source_manager
    value=source_manager.version_payload(version_id)
    if not value or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',filename):
        raise ValueError('Derivado no disponible.')
    item=value['version'].get('vector_artifacts',{}).get(filename)
    if not isinstance(item,dict):raise ValueError('Derivado no disponible.')
    key=item.get('object_key','')
    expected='geollaqta/maestro/derivados/'+value['version']['original']['sha256']+'/'
    if not re.fullmatch(re.escape(expected)+r'[a-f0-9]{64}/'+re.escape(filename),key):
        raise ValueError('Referencia de derivado no válida.')
    body,_=R2().get(key)
    if hashlib.sha256(body).hexdigest()!=item['sha256'] or len(body)!=item['size']:
        raise StorageError('El derivado no coincide con su huella archivada.')
    return body,item['content_type']
