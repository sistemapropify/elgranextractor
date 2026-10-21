"""Local authoring, private D1 persistence and R2 originals; working files stay in RAM."""
import os
from pathlib import Path
from threading import RLock

from .master_store import MasterStore

_store = None
_lock = RLock()
_pdfs = {}


def retain_pdf(version_id, body):
    with _lock:
        total = sum(len(value) for key,value in _pdfs.items() if key != version_id)
        if total + len(body) > 192 * 1024 * 1024:
            raise ValueError('Se alcanzó el límite de PDF en memoria. Conserva los originales; no se usarán archivos temporales.')
        _pdfs[version_id] = body


def pdf(version_id):
    with _lock:
        body = _pdfs.get(version_id)
    if body is not None or not durable():
        return body
    payload=version_payload(version_id)
    if not payload:return None
    import re,hashlib
    original=payload.get('version',{}).get('original',{})
    key=original.get('object_key','')
    if not re.fullmatch(r'geollaqta/maestro/originales/[a-f0-9]{64}\.pdf',key):return None
    from .storage import R2,StorageError
    body,_=R2().get(key)
    if hashlib.sha256(body).hexdigest()!=original.get('sha256'):
        raise StorageError('El PDF archivado no coincide con la huella de la versión.')
    retain_pdf(version_id,body)
    return body


def durable():
    return os.environ.get('CATASTRO_MASTER_STORAGE')=='d1'


def has_pdf(version_id):
    with _lock:
        if version_id in _pdfs:return True
    if not durable():return False
    payload=version_payload(version_id)
    return bool(payload and payload.get('version',{}).get('original',{}).get('object_key'))


def version_payload(version_id):
    import json
    value=store()
    with value.lock:
        row=value.db.execute('SELECT payload FROM versions WHERE id=?',(version_id,)).fetchone()
    if row:return json.loads(row[0])
    return value.version_payload(version_id) if durable() else None


def stage_pdf(payload, expected_revision, actor, body):
    with _lock:
        vid = payload['version']['id']
        if sum(len(value) for key,value in _pdfs.items() if key != vid) + len(body) > 192 * 1024 * 1024:
            raise ValueError('Se alcanzó el límite de PDF en memoria; conserva los originales.')
        if durable():
            from .storage import R2
            original=payload['version']['original']
            key='geollaqta/maestro/originales/'+original['sha256']+'.pdf'
            R2().put_verified(key,body,'application/pdf')
            original.update(object_key=key,archive_status='verified_r2')
        result = store().stage(payload,expected_revision,actor)
        retain_pdf(vid,body)
        return result


def enabled():
    configured = os.environ.get('CATASTRO_MASTER_ENABLED')
    if configured is not None:
        return configured == '1'
    return os.environ.get('CATASTRO_MASTER_LOCAL_PREVIEW') == '1'


def store():
    global _store
    if _store is not None:
        return _store
    with _lock:
        if _store is None:
            if durable():
                from .master_d1 import D1Store
                value=D1Store()
            else:
                value = MasterStore()
            value.project('cayma-pdf', 'Cayma · ensamblaje de planos', '040103', 34)
            value.stage({'source': {'id': 'cayma-pud-2006-eu03',
                'name': 'Cayma · plano antiguo conservado como respaldo', 'ubigeo': '040103', 'role': 'backup'},
                'version': {'id': 'cayma-eu03-original', 'label': 'Referencia 2006', 'source_date': '2006-08',
                    'crs': 'EPSG:4326', 'georeferencing': {'status': 'pending'},
                    'original': {'name': 'Plano municipal EU-03 (2006)'}}, 'features': []}, value.revision, 'sistema')
            supplied = os.environ.get('CATASTRO_MASTER_SEED_PDF')
            if supplied and Path(supplied).is_file():
                from .pdf_inspection import inspect
                path = Path(supplied)
                body = path.read_bytes()
                metadata = inspect(body)
                payload={'source': {'id':'cayma-sector-32','name':'Cayma · sector 32 · PDF aportado',
                    'ubigeo':'040103','project_id':'cayma-pdf','sheet_code':'Sector 32'},
                    'version': {'id':'cayma-sector-32:'+metadata['sha256'][:24], 'label':'Original aportado',
                        'source_date':'2017-01','crs':None,'georeferencing':{'status':'pending'},
                        'original':{'name':path.name,'sha256':metadata['sha256'],'archive_status':'not_uploaded'}},
                    'features':[], 'inspection':metadata}
                if durable():
                    from .storage import R2
                    original=payload['version']['original']
                    key='geollaqta/maestro/originales/'+metadata['sha256']+'.pdf'
                    known=value.db.execute('SELECT original_sha256 FROM versions WHERE id=?',
                        (payload['version']['id'],)).fetchone()
                    if not known or known[0]!=metadata['sha256']:
                        R2().put_verified(key,body,'application/pdf')
                    original.update(object_key=key,archive_status='verified_r2')
                value.stage(payload, value.revision, 'sistema')
                retain_pdf('cayma-sector-32:'+metadata['sha256'][:24],body)
            _store = value
        return _store
