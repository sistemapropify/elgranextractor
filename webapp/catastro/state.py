"""Local resumable work ledger, independent of Azure's property database."""
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]


def data_dir():
    return Path(os.environ.get('CATASTRO_DATA_DIR', str(ROOT / 'outputs/geollaqta-archive')))


class State:
    def __init__(self, root=None, memory=False):
        if memory:
            from .memory_files import MemoryPath
            self.root = MemoryPath()
            database = ':memory:'
        else:
            self.root = Path(root or data_dir())
            self.root.mkdir(parents=True, exist_ok=True)
            configured_db = os.environ.get('CATASTRO_STATE_DB') if root is None else None
            database = Path(configured_db).expanduser() if configured_db else self.root / 'estado.sqlite3'
            if configured_db and not database.is_file() and (self.root / 'estado.sqlite3').is_file():
                raise RuntimeError('El índice configurado necesita migración; el seguimiento anterior se conserva.')
            database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=' + ('MEMORY' if memory else 'WAL'))
        if memory:self.db.execute('PRAGMA temp_store=MEMORY')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS lots (
                lot_id TEXT PRIMARY KEY, ubigeo TEXT NOT NULL, object_id INTEGER,
                status TEXT NOT NULL, uploaded INTEGER DEFAULT 0, missing INTEGER DEFAULT 0,
                reports INTEGER DEFAULT 0, photos INTEGER DEFAULT 0, bytes INTEGER DEFAULT 0,
                updated REAL NOT NULL, error TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS uploads (
                object_key TEXT PRIMARY KEY, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, ubigeo TEXT NOT NULL, limit_lots INTEGER NOT NULL,
                lot_id TEXT, retry_missing INTEGER NOT NULL, status TEXT NOT NULL,
                created REAL NOT NULL, heartbeat REAL NOT NULL, processed INTEGER DEFAULT 0,
                message TEXT DEFAULT '', stop INTEGER DEFAULT 0, pid INTEGER);
        ''')
        # Additive upgrade: keep old bounded jobs and existing archive intact.
        columns = {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}
        for column in ('source_objects', 'skipped_objects', 'selected_objects', 'remaining_objects'):
            if column not in columns:
                try:
                    self.db.execute(f'ALTER TABLE jobs ADD COLUMN {column} INTEGER DEFAULT 0')
                except sqlite3.OperationalError:
                    if column not in {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}:
                        raise
        for column, definition in [('executor', "TEXT NOT NULL DEFAULT 'server'"), ('lease', "TEXT DEFAULT ''")]:
            if column not in {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}:
                try:
                    self.db.execute(f'ALTER TABLE jobs ADD COLUMN {column} {definition}')
                except sqlite3.OperationalError:
                    if column not in {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}:
                        raise
        self.db.execute('CREATE TABLE IF NOT EXISTS collector_presence (id INTEGER PRIMARY KEY CHECK(id=1), heartbeat REAL NOT NULL)')
        if 'source_status' not in {r['name'] for r in self.db.execute('PRAGMA table_info(collector_presence)')}:
            try:
                self.db.execute("ALTER TABLE collector_presence ADD COLUMN source_status TEXT DEFAULT 'unchecked'")
            except sqlite3.OperationalError:
                if 'source_status' not in {r['name'] for r in self.db.execute('PRAGMA table_info(collector_presence)')}:
                    raise
        self.db.execute('CREATE INDEX IF NOT EXISTS lots_updated ON lots(updated)')
        if 'workers' not in {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}:
            try:
                self.db.execute('ALTER TABLE jobs ADD COLUMN workers INTEGER NOT NULL DEFAULT 1')
            except sqlite3.OperationalError:
                if 'workers' not in {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}:
                    raise
        self.db.commit()

    def close(self):
        self.db.close()

    def lot(self, lot_id):
        row = self.db.execute('SELECT * FROM lots WHERE lot_id=?', (lot_id,)).fetchone()
        return dict(row) if row else None

    def save_lot(self, lot_id, ubigeo, commit=True, **values):
        base = dict(object_id=None, status='failed', uploaded=0, missing=0, reports=0,
                    photos=0, bytes=0, error='', updated=time.time())
        base.update(values)
        self.db.execute('INSERT OR REPLACE INTO lots VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (lot_id, ubigeo, *(base[k] for k in ('object_id','status','uploaded','missing',
                                                         'reports','photos','bytes','updated','error'))))
        if commit:
            self.db.commit()

    def save_upload(self, key, digest, size, commit=True):
        self.db.execute('INSERT OR REPLACE INTO uploads VALUES (?,?,?)', (key, digest, size))
        if commit:
            self.db.commit()

    def uploaded_hash(self, key):
        row = self.db.execute('SELECT sha256 FROM uploads WHERE object_key=?', (key,)).fetchone()
        return row[0] if row else None

    def upload_bytes(self):
        return self.db.execute('SELECT COALESCE(SUM(bytes),0) FROM uploads').fetchone()[0]

    def set_lot_bytes(self, lot_id, size):
        self.db.execute('UPDATE lots SET bytes=? WHERE lot_id=?', (size, lot_id))
        self.db.commit()

    def create_job(self, ubigeo, limit_lots, lot_id=None, retry_missing=False, executor='server', workers=10):
        from .parallel import worker_count
        workers = worker_count(workers)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            active = self.db.execute("SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY created DESC LIMIT 1").fetchone()
            if active:
                if active['heartbeat'] > time.time() - 300 or (active['executor'] == 'external' and active['status'] == 'queued'):
                    raise ValueError('Ya hay una descarga en curso. Espera o detenla antes de iniciar otra.')
                self.db.execute("UPDATE jobs SET status='interrupted',message='Ejecución interrumpida; puede reanudarse.' WHERE id=?", (active['id'],))
            job_id = uuid.uuid4().hex
            self.db.execute('INSERT INTO jobs (id,ubigeo,limit_lots,lot_id,retry_missing,status,created,heartbeat) VALUES (?,?,?,?,?,?,?,?)',
                            (job_id, ubigeo, limit_lots, lot_id, int(retry_missing), 'queued', time.time(), time.time()))
            self.db.execute('UPDATE jobs SET executor=?,workers=? WHERE id=?', (executor, workers, job_id))
            self.db.commit()
            return job_id
        except Exception:
            self.db.rollback()
            raise

    def job(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        return dict(row) if row else None

    def update_job(self, job_id, **values):
        allowed = {'status', 'heartbeat', 'processed', 'message', 'stop', 'pid',
                   'source_objects', 'skipped_objects', 'selected_objects', 'remaining_objects'}
        if not values.keys() <= allowed:
            raise ValueError('Campos de ejecución no válidos.')
        values['heartbeat'] = time.time()
        self.db.execute('UPDATE jobs SET ' + ','.join(k + '=?' for k in values) + ' WHERE id=?',
                        (*values.values(), job_id))
        self.db.commit()

    def snapshot(self, ubigeo=None):
        where, args = ('WHERE ubigeo=?', (ubigeo,)) if ubigeo else ('', ())
        totals = self.db.execute('SELECT COUNT(*) lots,COALESCE(SUM(reports),0) reports,COALESCE(SUM(photos),0) photos, '
                                'COALESCE(SUM(missing),0) missing,COALESCE(SUM(uploaded),0) uploaded,COALESCE(SUM(bytes),0) bytes FROM lots ' + where, args).fetchone()
        lots = [dict(r) for r in self.db.execute('SELECT * FROM lots ' + where + ' ORDER BY updated DESC LIMIT 50', args)]
        jobs = [dict(r) for r in self.db.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 10')]
        for job in jobs:
            job.pop('lease', None)
            if job['status'] in ('queued', 'running') and job['heartbeat'] < time.time() - 300 and not (job['executor'] == 'external' and job['status'] == 'queued'):
                self.update_job(job['id'], status='interrupted', message='Ejecución interrumpida; puede reanudarse.')
                job['status'] = 'interrupted'
        return {'totals': dict(totals), 'lots': lots, 'jobs': jobs, 'r2_bytes': self.upload_bytes()}
