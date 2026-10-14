"""Repair metadata from archived originals, without re-downloading COFOPRI."""
import hashlib
import json
from pathlib import Path
import time

from .state import State
from .storage import R2
from scrapi.geollaqta_scraper import atomic_write, pdf_pages, DEFAULT_BUDGET


def reextract(lot_id=None, root=None, r2=None):
    state = State(root)
    cloud = r2 or R2()
    try:
        if state.db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running') AND heartbeat>?", (time.time()-300,)).fetchone():
            raise ValueError('Espera a que termine la descarga activa antes de actualizar los datos.')
        rows = list(state.db.execute('SELECT * FROM lots' + (' WHERE lot_id=?' if lot_id else ''), (lot_id,) if lot_id else ()))
        result = []
        for row in rows:
            folder = state.root / row['ubigeo'] / row['lot_id']
            path = folder / 'datos.json'
            data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else json.loads(cloud.get('geollaqta/'+row['ubigeo']+'/'+row['lot_id']+'/datos.json')[0])
            artifacts = {a['filename']:a for a in data['artifacts']}
            fields = 0
            for report in data['reports']:
                pdf_path = folder / report['filename']
                original = pdf_path.read_bytes() if pdf_path.is_file() else cloud.get('geollaqta/'+row['ubigeo']+'/'+row['lot_id']+'/'+report['filename'])[0]
                if hashlib.sha256(original).hexdigest() != artifacts[report['filename']]['sha256']:
                    raise ValueError('La copia original no coincide con su hash; no se actualizarán los datos.')
                report['pages'] = pdf_pages(original)
                fields += sum(len(p.get('named_fields',[]))+len(p.get('numbered_fields',[])) for p in report['pages'])
            data['extraction_revision'] = 2
            data['extracted_at'] = time.time()
            body = json.dumps(data,ensure_ascii=False,indent=2).encode()
            snapshot = 'datos-' + hashlib.sha256(body).hexdigest()[:16] + '.json'
            if DEFAULT_BUDGET is not None and state.upload_bytes() + 2*len(body) > DEFAULT_BUDGET:
                raise ValueError('La actualización excedería el límite de almacenamiento del recolector.')
            if row['uploaded']:
                for name in (snapshot, 'datos.json'):
                    key = 'geollaqta/'+row['ubigeo']+'/'+row['lot_id']+'/'+name
                    cloud.put_verified(key, body, 'application/json')
                    state.save_upload(key, hashlib.sha256(body).hexdigest(),len(body))
            folder.mkdir(parents=True, exist_ok=True)
            atomic_write(folder/snapshot,body)
            atomic_write(path,body)
            state.db.execute('UPDATE lots SET bytes=?,updated=? WHERE lot_id=?',
                             (sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),time.time(),row['lot_id']))
            state.db.commit()
            result.append({'lot_id':row['lot_id'],'documents':len(data['reports']),'fields':fields,'uploaded':bool(row['uploaded'])})
        return result
    finally:
        state.close()
