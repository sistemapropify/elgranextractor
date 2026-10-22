"""Index only newly acknowledged collector output; never scan old JSON records."""
import hashlib
import json
import re
from .master_store import Conflict
from .storage import R2,StorageError
from .master_ingest import prepare


def stage_archived_lot(ubigeo,lot_id,store,cloud=None):
    if not re.fullmatch(r'[0-9]{6}',ubigeo) or not re.fullmatch(ubigeo+r'[0-9]{8,12}',lot_id):
        raise ValueError('Lote no válido para indexación.')
    cloud=cloud or R2()
    prefix='geollaqta/'+ubigeo+'/'+lot_id+'/'
    body,_=cloud.get(prefix+'datos.json')
    digest=hashlib.sha256(body).hexdigest();snapshot=prefix+'datos-'+digest+'.json'
    try:
        immutable,_=cloud.get(snapshot)
    except StorageError as error:
        if error.http_status != 404:
            raise
        # Older collector acknowledgements can reference a snapshot that was
        # never persisted. The hash-addressed bytes still exist as datos.json;
        # repair the immutable object instead of making COFOPRI redownload it.
        cloud.put_verified(snapshot,body,'application/json')
        immutable=body
    if hashlib.sha256(immutable).hexdigest()!=digest:
        raise StorageError('El original inmutable no coincide con el manifiesto confirmado.')
    manifest=json.loads(immutable)
    if manifest.get('lot_id')!=lot_id or manifest.get('district_ubigeo')!=ubigeo:
        raise ValueError('El manifiesto no corresponde al lote confirmado.')
    if manifest.get('extraction_revision',0)<3:
        raise ValueError('La migración de extracciones históricas permanece bloqueada.')
    payload=prepare(manifest)
    payload['version']['original'].update(object_key=snapshot,sha256=digest,archive_status='verified_r2')
    for attempt in range(3):
        try:
            if hasattr(store,'refresh'):store.refresh()
            return store.stage(payload,store.revision,'colector-cofopri')
        except Conflict:
            if attempt==2:raise
