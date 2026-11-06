"""Import every archived complete/partial lot expedient into D1."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from django.conf import settings

WORK = Path(r'D:\PROMETEO\catastro_completo')
os.environ['CATASTRO_STATE_DB'] = str(WORK / 'estado.sqlite3')
os.environ['CATASTRO_DATA_DIR'] = str(WORK / 'trabajo')

if not settings.configured:
    settings.configure(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    })

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp'))

from catastro.manifest_migration import migrate_manifests_direct
from catastro.master_d1 import Gateway
from catastro.master_store import Conflict
from catastro.state import State
from catastro.storage import StorageError
from cuadrantizacion.geollaqta import DISTRICTS

OUTPUT = Path(
    r'D:\PROMETEO\catastro_completo\expedientes_d1_resultado.json')


def main():
    gateway = Gateway()
    state = State()
    results = []
    failures = []
    lots = [
        dict(row) for row in state.db.execute(
            '''SELECT lot_id,ubigeo,status,uploaded
               FROM lots
               WHERE uploaded=1 AND status IN ('complete','partial')
               ORDER BY ubigeo,lot_id'''
        )
    ]
    state.close()
    by_district = {}
    for lot in lots:
        by_district.setdefault(lot['ubigeo'], []).append(lot['lot_id'])
    print(
        'TOTAL', len(lots), 'DISTRICTS', len(by_district),
        flush=True,
    )
    for district, district_lots in sorted(by_district.items()):
        offset = 0
        batch_size = 5
        while offset < len(district_lots):
            chunk = district_lots[offset:offset + batch_size]
            started = time.monotonic()
            try:
                result = migrate_manifests_direct(
                    gateway,
                    district,
                    DISTRICTS[district]['name'],
                    chunk,
                    actor='carga-completa-catastro-maestro',
                )
                results.append({
                    **result,
                    'seconds': round(time.monotonic() - started, 1),
                })
                print(
                    'DONE', district,
                    min(offset + len(chunk), len(district_lots)),
                    len(district_lots), result['revision'],
                    flush=True,
                )
                offset += len(chunk)
                batch_size = 5
                time.sleep(1)
            except Exception as error:
                if isinstance(error, Conflict):
                    print(
                        'RETRY_CONFLICT', district, offset,
                        flush=True,
                    )
                    time.sleep(3)
                    continue
                if (isinstance(error, StorageError)
                        and 'excede los límites' in str(error)
                        and batch_size > 1):
                    batch_size = max(1, batch_size // 2)
                    print(
                        'RETRY_SMALLER', district, offset, batch_size,
                        flush=True,
                    )
                    continue
                failures.append({
                    'ubigeo': district,
                    'lots': chunk,
                    'error': str(error),
                })
                print(
                    'ERROR', district, offset, type(error).__name__,
                    str(error), flush=True,
                )
                offset += len(chunk)
            OUTPUT.write_text(
                json.dumps(
                    {'results': results, 'failures': failures},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding='utf-8',
            )
    print(
        'FINAL',
        json.dumps({
            'processed_batches': len(results),
            'processed_lots': sum(item.get('lots', 0) for item in results),
            'failures': len(failures),
        }),
        flush=True,
    )
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
