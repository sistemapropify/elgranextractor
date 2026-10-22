"""District-scoped COFOPRI collector; originals and extracted data go to R2.

The runner is independent of Django, property listings and browser sessions.
Unavailable individual fichas remain explicitly pending, never synthesized.
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import threading
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener

from catastro.state import State
from catastro.parallel import Coordinator, CoordinatorState, RequestGate, worker_count
from catastro.storage import NoRedirect, R2, StorageError

PORTAL = 'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/'
SERVICE = 'https://geoportal.cofopri.gob.pe/giscofopri/rest/services/Cofopri/Catastro_PCDPI/MapServer/10/query'
CATALOG = json.loads((Path(__file__).resolve().parents[1] / 'cuadrantizacion/geollaqta_districts.json').read_text(encoding='utf-8'))
DISTRICTS = {d['ubigeo']: d for d in CATALOG['districts']}
MAX_FILE = 20_000_000
DEFAULT_BUDGET = None


class CollectionError(RuntimeError):
    def __init__(self, message, http_status=None):
        super().__init__(message)
        self.http_status = http_status


class Stopped(CollectionError):
    pass


def validate(ubigeo, limit=None, lot_id=None):
    if ubigeo not in DISTRICTS:
        raise ValueError('Selecciona un distrito del catálogo de Arequipa.')
    if limit is not None and (isinstance(limit, bool) or not 1 <= int(limit) <= 500):
        raise ValueError('El lote de descarga debe contener entre 1 y 500 predios.')
    if lot_id and not re.fullmatch(ubigeo + r'\d{8,12}', lot_id):
        raise ValueError('El código del lote no pertenece al distrito seleccionado.')


class GalleryLinks(HTMLParser):
    def __init__(self, ubigeo):
        super().__init__()
        self.ubigeo = ubigeo
        self.images, self.reports, self.records = [], [], []
        self.documents = []
        self.row_cells = None
        self.cell_text = None
        self.row_links = []
        self.link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.row_cells, self.row_links = [], []
        if tag == 'td' and self.row_cells is not None:
            self.cell_text = []
        if tag == 'a' and self.row_cells is not None:
            self.link = {'url': urljoin(PORTAL, attrs.get('href', '')), 'text': []}
        for value in ([attrs.get('src'), attrs.get('data-image')] if tag == 'img' else
                      [attrs.get('href'), attrs.get('data-image')] if tag == 'a' else []):
            if not value:
                continue
            url = urljoin(PORTAL, value)
            p = urlsplit(url)
            if p.scheme != 'https' or p.netloc != 'catastro.cofopri.gob.pe' or p.fragment:
                continue
            if re.fullmatch(r'/img_catastro/' + self.ubigeo + r'/[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png)', p.path, re.I) and not p.query:
                target = self.images
            elif re.fullmatch('id=' + self.ubigeo + r'\d{13}', p.query):
                target = (self.reports if p.path == '/geollaqta/reportefichas/vistapdf/reporte.php' else
                          self.records if re.fullmatch(r'/geollaqta/reportefichas/vistapdf/ficha[a-z0-9]{1,12}\.php', p.path) else None)
                if target is None:
                    continue
            else:
                continue
            if url not in target:
                target.append(url)

    def handle_data(self, data):
        if self.cell_text is not None:
            self.cell_text.append(data)
        if self.link is not None:
            self.link['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.link:
            self.row_links.append(self.link)
            self.link = None
        if tag == 'td' and self.cell_text is not None:
            self.row_cells.append(' '.join(''.join(self.cell_text).split()))
            self.cell_text = None
        if tag == 'tr' and self.row_cells is not None:
            for link in self.row_links:
                if link['url'] not in self.records + self.reports:
                    continue
                text = ' '.join(''.join(link['text']).split())
                report = link['url'] in self.reports
                name = 'REPORTE CATASTRAL' if report else text or 'FICHA CATASTRAL'
                self.documents.append({'source_url': link['url'], 'document_name': name,
                                       'form_number': self.row_cells[1] if len(self.row_cells) > 1 else '',
                                       'record_id': urlsplit(link['url']).query.split('=', 1)[1],
                                       'type': 'cadastral_report_pdf' if report else 'individual_record_pdf' if 'INDIVIDUAL' in name else 'cadastral_form_pdf'})
            self.row_cells = None


class Source:
    def __init__(self, checkpoint=lambda: None, delay=1, timeout=25, gate=None):
        self.checkpoint = checkpoint
        self.delay = max(1, delay)
        self.last_request = 0
        self.timeout = max(1, min(float(timeout), 25))
        self.opener = build_opener(NoRedirect())
        self.gate = gate

    def get(self, url, params=None, retry=True):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc not in ('catastro.cofopri.gob.pe', 'geoportal.cofopri.gob.pe'):
            raise CollectionError('Origen de descarga no permitido.')
        for attempt in range(3 if retry else 1):
            self.checkpoint()
            if self.gate:
                self.gate.wait(self.checkpoint)
            else:
                time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            self.checkpoint()
            self.last_request = time.monotonic()
            req = Request(url, data=urlencode(params).encode() if params else None,
                          headers={'User-Agent': 'Prometeo-Catastro/1.0', 'Accept': '*/*'})
            try:
                with self.opener.open(req, timeout=self.timeout) as response:
                    data = response.read(MAX_FILE + 1)
                if len(data) > MAX_FILE:
                    raise CollectionError('Archivo superior a 20 MB; queda pendiente.')
                return data
            except HTTPError as exc:
                if exc.code == 429 and self.gate:
                    try:
                        retry_after = (exc.headers or {}).get('Retry-After', '')
                        wait = float(retry_after)
                    except (ValueError, TypeError):
                        try:
                            wait = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                        except (ValueError, TypeError, OverflowError):
                            wait = 2 ** (attempt + 1)
                    self.gate.defer(wait)
                if exc.code in (401, 403):
                    raise CollectionError('COFOPRI requiere acceso o rechazó la descarga; ejecución detenida.', exc.code) from None
                if attempt == (2 if retry else 0) or exc.code not in (429, 500, 502, 503, 504):
                    raise CollectionError('COFOPRI respondió HTTP ' + str(exc.code) + '.', exc.code) from None
            except (URLError, TimeoutError, OSError):
                if attempt == (2 if retry else 0):
                    raise CollectionError('No se pudo conectar con COFOPRI.') from None
            time.sleep(2 ** (attempt + 1))

    def query(self, **params):
        try:
            data = json.loads(self.get(SERVICE, {'f': 'json', **params}))
        except (ValueError, UnicodeError):
            raise CollectionError('COFOPRI devolvió una consulta no válida.') from None
        if not isinstance(data, dict) or data.get('error'):
            raise CollectionError('COFOPRI no pudo completar la consulta catastral.')
        return data


def pdf_pages(data):
    try:
        import fitz
        from catastro.pdf_fields import extract_page
        with fitz.open(stream=data, filetype='pdf') as doc:
            return [{'number': i + 1, 'text': page.get_text(sort=True),
                     'tables': [table.extract() for table in page.find_tables().tables], **extract_page(page)}
                    for i, page in enumerate(doc)]
    except ImportError:
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as doc:
            return [{'number': i + 1, 'text': page.extract_text() or '', 'tables': page.extract_tables()}
                    for i, page in enumerate(doc.pages)]


def check_pdf_runtime():
    import importlib.util
    if not any(importlib.util.find_spec(name) for name in ('fitz', 'pdfplumber')):
        raise CollectionError('Instala PyMuPDF o pdfplumber en el entorno del recolector.')


def valid_body(kind, data):
    if kind.endswith('pdf'):
        return data.lstrip().startswith(b'%PDF-')
    if kind == 'facade_image':
        return data.startswith(b'\xff\xd8\xff') or data.startswith(b'\x89PNG\r\n\x1a\n')
    return bool(data)


def atomic_write(path, body):
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(body)
    temp.replace(path)


def _archive_lot(feature, ubigeo, state, source, r2, upload, keep_local, checkpoint,
                 parse_pdf, budget=None, disk_bytes=0):
    attrs = feature['attributes']
    code = str(attrs['ID_LOTE']).strip()
    folder = state.root / ubigeo / code
    folder.mkdir(parents=True, exist_ok=True)
    existing_files = {p.name for p in folder.iterdir() if p.is_file()}
    manifest_path = folder / 'datos.json'
    stored_lot = state.lot(code)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    elif stored_lot and stored_lot['uploaded'] and upload:
        body, _ = r2.get('geollaqta/' + ubigeo + '/' + code + '/datos.json')
        manifest = json.loads(body)
    else:
        manifest = {}
    prior = {a['filename']: a for a in manifest.get('artifacts', [])}
    artifacts, missing, reports = [], [], []
    gallery_url = PORTAL + 'vistadetalle.php?' + urlencode({'id_lote': code})

    def artifact(kind, filename, url, retry=True, document=None):
        nonlocal disk_bytes
        checkpoint()
        path = folder / filename
        previous = next((a for a in prior.values() if a['source_url'] == url), None)
        if previous:
            filename = previous['filename']
            path = folder / filename
        body = path.read_bytes() if path.is_file() else None
        key = 'geollaqta/' + ubigeo + '/' + code + '/' + filename
        if body is None and previous and upload and (state.uploaded_hash(key) == previous['sha256'] or (stored_lot and stored_lot['uploaded'])):
            body, _ = r2.get(key)
            if hashlib.sha256(body).hexdigest() != previous['sha256']:
                raise StorageError('El original archivado en R2 no coincide con su hash.')
            state.save_upload(key, previous['sha256'], len(body))
            atomic_write(path, body)
            disk_bytes += len(body)
        cached = body is not None and previous and previous['source_url'] == url and previous['sha256'] == hashlib.sha256(body).hexdigest()
        if not cached:
            body = source.get(url, retry=retry)
            if not valid_body(kind, body):
                raise CollectionError('El documento recibido no tiene el formato esperado.')
            if budget is not None and disk_bytes + len(body) > budget:
                raise CollectionError('Se alcanzó el límite local de almacenamiento del piloto.')
            stem, suffix = Path(filename).stem, Path(filename).suffix
            if previous:
                stem = re.sub(r'-[a-f0-9]{16}$', '', stem)
            filename = stem + '-' + hashlib.sha256(body).hexdigest()[:16] + suffix
            path = folder / filename
            atomic_write(path, body)
            disk_bytes += len(body)
        info = {'type': kind, 'filename': filename, 'source_url': url, 'bytes': len(body),
                'sha256': hashlib.sha256(body).hexdigest()}
        if document:
            info.update(document_name=document['document_name'], form_number=document['form_number'], record_id=document['record_id'])
        artifacts.append(info)
        return body

    fatal = None
    try:
        html = artifact('source_html', 'detalle.html', gallery_url)
        parser = GalleryLinks(ubigeo)
        parser.feed(html.decode('utf-8', errors='replace'))
        if not parser.reports and not parser.records:
            missing.append({'type': 'gallery', 'source_url': gallery_url, 'error': 'No hay reportes ni fichas publicados en la galería.'})
        documents = parser.documents + [{'type': 'facade_image', 'source_url': url} for url in parser.images]
        for document in documents:
                kind, url = document['type'], document['source_url']
                filename = (('reporte-' if kind == 'cadastral_report_pdf' else 'ficha-') + document['record_id'] + '.pdf' if kind.endswith('pdf') else urlsplit(url).path.rsplit('/', 1)[1])
                try:
                    body = artifact(kind, filename, url, retry=not kind.endswith('record_pdf'), document=document if kind.endswith('pdf') else None)
                    if kind.endswith('pdf'):
                        reports.append({**document, 'filename': artifacts[-1]['filename'], 'pages': parse_pdf(body)})
                except Stopped:
                    raise
                except (CollectionError, ValueError, RuntimeError) as exc:
                    if isinstance(exc, StorageError):
                        raise
                    missing.append({**document, 'error': str(exc), 'http_status': getattr(exc, 'http_status', None)})
                    if 'rechazó' in str(exc):
                        raise
        if not parser.images:
            missing.append({'type': 'facade_image', 'source_url': gallery_url, 'error': 'La galería no contiene fotografías publicadas.'})
    except Stopped:
        raise
    except CollectionError as exc:
        # An unavailable gallery belongs to this property only. Keep
        # collecting the other properties, while stopping on denied
        # access or a connection failure affecting the whole source.
        if exc.http_status not in (404, 410, 500, 502, 503, 504):
            fatal = str(exc)
        missing.append({'type': 'source_html', 'source_url': gallery_url, 'error': str(exc), 'http_status': exc.http_status})
    manifest = {'schema_version': 1, 'extraction_revision': 2, 'lot_id': code, 'district_ubigeo': ubigeo,
                'source_url': gallery_url, 'retrieved_at': time.time(),
                'feature': feature, 'artifacts': artifacts, 'reports': reports, 'missing': missing}
    atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    snapshot_name = 'datos-' + hashlib.sha256(manifest_path.read_bytes()).hexdigest() + '.json'
    atomic_write(folder / snapshot_name, manifest_path.read_bytes())
    cloud_ok = False
    try:
        if upload:
            for filename in [a['filename'] for a in artifacts] + [snapshot_name, 'datos.json']:
                checkpoint()
                body = (folder / filename).read_bytes()
                digest = hashlib.sha256(body).hexdigest()
                key = 'geollaqta/' + ubigeo + '/' + code + '/' + filename
                if state.uploaded_hash(key) == digest:
                    continue
                if budget is not None and state.upload_bytes() + len(body) > budget:
                    raise StorageError('Se alcanzó el límite de almacenamiento configurado; la carga queda pendiente.')
                mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                r2.put_verified(key, body, mime)
                state.save_upload(key, digest, len(body))
            cloud_ok = True
    except StorageError as exc:
        fatal = str(exc)
    status = 'failed' if fatal else 'partial' if missing else 'complete'
    state.save_lot(code, ubigeo, object_id=attrs.get('OBJECTID'), status=status, uploaded=int(cloud_ok),
                   missing=len(missing), reports=sum(a['type'].endswith('pdf') for a in artifacts),
                   photos=sum(a['type'] == 'facade_image' for a in artifacts),
                   bytes=sum(p.stat().st_size for p in folder.iterdir() if p.is_file()), error=fatal or '')
    if cloud_ok and not keep_local and not fatal:
        # Only remove new working copies, after PUT/HEAD verification.
        # Existing local review files and all remote versions are kept.
        for filename in {a['filename'] for a in artifacts} | {snapshot_name, 'datos.json'}:
            path = folder / filename
            if filename not in existing_files and path.is_file():
                disk_bytes -= path.stat().st_size
                path.unlink()
        state.set_lot_bytes(code, sum(p.stat().st_size for p in folder.iterdir() if p.is_file()))
        if not any(folder.iterdir()):
            folder.rmdir()
    return {'lot_id': code, 'uploaded': int(cloud_ok), 'partial': int(status == 'partial'),
            'failed': int(status == 'failed'), 'fatal': fatal, 'disk_bytes': disk_bytes}


def collect(ubigeo, max_lotes=None, lot_id=None, retry_missing=False, upload=True,
            root=None, r2=None, source=None, progress=None, checkpoint=lambda: None,
            budget=DEFAULT_BUDGET, keep_local=None, workers=None, state=None):
    validate(ubigeo, max_lotes, lot_id)
    check_pdf_runtime()
    workers = worker_count(workers)
    # A legacy byte-capped pilot keeps its exact sequential budget accounting.
    if budget is not None:
        workers = 1
    owns_state = state is None
    state = state or State(root)
    source = source or Source(checkpoint)
    gate = RequestGate(interval=source.delay) if isinstance(source, Source) else None
    if gate:
        source.gate = gate
    r2 = (r2 or R2()) if upload else None
    keep_local = bool(not os.environ.get('WEBSITE_SITE_NAME')) if keep_local is None else keep_local
    keep_local = keep_local or not upload
    summary = {'ubigeo': ubigeo, 'processed': 0, 'uploaded': 0, 'partial': 0,
               'failed': 0, 'skipped': 0, 'complete': False, 'stop_reason': 'batch_limit', 'scope': 'lot' if lot_id else 'district'}
    disk_bytes = sum(p.stat().st_size for p in state.root.rglob('*') if p.is_file()) if budget is not None else 0

    def event(message):
        if progress:
            progress({**summary, 'message': message})

    try:
        where = "ID_DIST='" + ubigeo + "'"
        if lot_id:
            where += " AND ID_LOTE='" + lot_id + "'"
        ids_reply = source.query(where=where, returnIdsOnly='true')
        if 'objectIds' not in ids_reply:
            raise CollectionError('COFOPRI no devolvió el inventario de lotes.')
        ids = sorted(set(ids_reply['objectIds'] or []))
        summary['source_objects'] = len(ids)
        done = {row['object_id'] for row in state.db.execute('SELECT * FROM lots WHERE ubigeo=?', (ubigeo,))
                if row['status'] in ('complete', 'partial') and (not upload or row['uploaded'])
                and (not retry_missing or not row['missing'])}
        pending = [i for i in ids if i not in done]
        selected = pending if max_lotes is None else pending[:int(max_lotes)]
        summary['skipped'] = len(ids) - len(pending)
        summary['selected_objects'] = len(selected)
        summary['remaining_objects'] = len(pending)
        initial_remaining = len(pending)
        event(f"Inventario: {len(ids)} registros; {summary['skipped']} ya archivados; "
              f"{len(selected)} por revisar en esta ejecución.")
        def features():
            # Stream small internal groups instead of keeping a whole district's
            # geometries in memory. The user starts only one district download.
            for start in range(0, len(selected), 100):
                checkpoint()
                data = source.query(objectIds=','.join(map(str, selected[start:start + 100])),
                                    outFields='*', returnGeometry='true', outSR=4326)
                batch = data.get('features', [])
                returned = {row.get('attributes', {}).get('OBJECTID') for row in batch}
                if data.get('exceededTransferLimit') or returned != set(selected[start:start + 100]):
                    raise CollectionError('COFOPRI devolvió un inventario incompleto; no se marcará como terminado.')
                yield from batch
        workers = min(workers, max(1, len(selected)))
        summary['workers'] = workers
        stopped = threading.Event()
        def worker_checkpoint():
            if stopped.is_set():
                raise Stopped('Descarga detenida; avance conservado para reanudar.')
            if workers == 1:
                checkpoint()
        coordinator = Coordinator(worker_checkpoint)
        ledger = CoordinatorState(state, coordinator)
        last_check = 0
        def check_control():
            nonlocal last_check
            if time.monotonic() - last_check >= .5:
                checkpoint()
                last_check = time.monotonic()
        def archive(feature):
            client = (Source(worker_checkpoint, source.delay, source.timeout, gate=gate)
                      if isinstance(source, Source) else source)
            cloud = R2(values=r2.values, timeout=r2.timeout) if isinstance(r2, R2) else r2
            return _archive_lot(feature, ubigeo, ledger, client, cloud, upload, keep_local,
                                worker_checkpoint, lambda body: coordinator.call(pdf_pages, body),
                                budget, disk_bytes)
        def sync_summary():
            for name in ('processed', 'uploaded', 'partial', 'failed'):
                summary[name] = ledger.totals[name]
            summary['remaining_objects'] = initial_remaining - ledger.totals['uploaded' if upload else 'local_saved']
        def record(result, notify=True):
            nonlocal disk_bytes
            disk_bytes = result['disk_bytes']
            sync_summary()
            message = result['lot_id'] + ': ' + ('archivado en R2' if result['uploaded'] else 'guardado localmente')
            if result['partial']:
                message += '; documentos pendientes'
            if result['fatal']:
                message += '; ' + result['fatal']
                summary['stop_reason'] = 'source_or_storage_error'
            if notify:
                event(message)
        seen = set()
        def validated_features():
            for feature in features():
                attrs = feature.get('attributes', {})
                code = str(attrs.get('ID_LOTE', '')).strip()
                if attrs.get('ID_DIST') != ubigeo or not re.fullmatch(ubigeo + r'\d{8,12}', code):
                    raise CollectionError('El lote consultado no corresponde al distrito.')
                if code not in seen:
                    seen.add(code)
                    yield feature
        failed = False
        if workers == 1:
            for feature in validated_features():
                checkpoint()
                result = archive(feature)
                record(result)
                if result['fatal']:
                    failed = True
                    break
        else:
            pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='catastro')
            pending = set()
            iterator = iter(validated_features())
            exhausted = False
            try:
                while pending or not exhausted:
                    check_control()
                    while not exhausted and len(pending) < workers:
                        try:
                            feature = next(iterator)
                        except StopIteration:
                            exhausted = True
                            break
                        pending.add(pool.submit(archive, feature))
                    coordinator.service(timeout=.05)
                    for future in list(pending):
                        if future.done():
                            pending.remove(future)
                            result = future.result()
                            record(result)
                            if result['fatal']:
                                failed = True
                    if failed:
                        break
            finally:
                stopped.set()
                for future in pending:
                    future.cancel()
                # Finish bounded in-flight I/O and service ledger acknowledgments.
                # Neither SQLite nor the PDF parser ever runs on a worker thread.
                while any(not future.done() for future in pending):
                    coordinator.service(timeout=.05)
                while coordinator.service():
                    pass
                pool.shutdown(wait=True, cancel_futures=True)
                for future in pending:
                    if not future.cancelled():
                        try:
                            result = future.result()
                        except Stopped:
                            continue
                        record(result, notify=False)
                        failed = failed or bool(result['fatal'])
            if failed:
                event('Descarga detenida por un error del origen o almacenamiento; avance conservado.')
        # A stop may arrive after a durable ledger commit but before a worker's
        # return. Final totals reflect those commits, including out-of-order I/O.
        sync_summary()
        if not failed:
            unresolved = state.lot(lot_id)['missing'] if lot_id and state.lot(lot_id) else state.snapshot(ubigeo)['totals']['missing']
            summary['complete'] = not summary['remaining_objects'] and not summary['partial'] and not summary['failed'] and not unresolved
            summary['stop_reason'] = 'finished' if summary['complete'] else 'pending_documents' if not summary['remaining_objects'] else 'batch_limit'
        return summary
    finally:
        if owns_state:
            state.close()
