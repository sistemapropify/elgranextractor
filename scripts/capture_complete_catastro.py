"""Archive every available COFOPRI expedient without on-demand retrieval."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(r'D:\PROMETEO\catastro_completo')
WORK.mkdir(parents=True, exist_ok=True)
os.environ['CATASTRO_DATA_DIR'] = str(WORK / 'trabajo')
os.environ['CATASTRO_STATE_DB'] = str(WORK / 'estado.sqlite3')
os.environ['CATASTRO_KEEP_LOCAL'] = '0'
os.environ['CATASTRO_MASTER_COLLECTION_ENABLED'] = '1'
os.environ['CATASTRO_MASTER_STORAGE'] = 'd1'
os.environ.setdefault('CATASTRO_MAX_WORKERS', '4')
sys.path.insert(0, str(ROOT / 'webapp'))

from catastro import cofopri_vector_migration, geollaqta_bulk, vector_snapshots
from catastro.formalization_detail_migration import (
    migrate_formalization_details,
)
from catastro.jobs import run_job, start_job
from catastro.master_d1 import Gateway
from catastro.state import State
from cuadrantizacion.geollaqta import DISTRICTS


def seed_existing(district):
    ids, truncated = geollaqta_bulk.lot_ids(district)
    state = State()
    try:
        for lot_id in ids:
            if state.lot(lot_id):
                continue
            state.save_lot(
                lot_id,
                district,
                status='complete',
                uploaded=1,
                missing=0,
                reports=0,
                photos=0,
            )
    finally:
        state.close()
    return len(ids), truncated


def pcdpi_districts():
    return sorted({
        row['ubigeo'] for row in vector_snapshots.inventory()['snapshots']
        if (row.get('source') or 'pcdpi') == 'pcdpi'
    })


def write_report(report):
    (WORK / 'captura_completa_resultado.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def capture_gallery_district(district, report):
    metadata = DISTRICTS[district]
    started = time.monotonic()
    print('GALLERY_START', district, metadata['name'], flush=True)
    try:
        archived, truncated = seed_existing(district)
        job_id = start_job(
            district,
            launch=False,
            workers=int(os.environ['CATASTRO_MAX_WORKERS']),
        )
        result = run_job(job_id)
        report['gallery_results'].append({
            'ubigeo': district,
            'district': metadata['name'],
            'job_id': job_id,
            'existing_archive_prefixes': archived,
            'inventory_truncated': truncated,
            'result': result,
            'seconds': round(time.monotonic() - started, 1),
        })
        print(
            'GALLERY_DONE', district, json.dumps(result, ensure_ascii=False),
            flush=True,
        )
    except Exception as error:
        report['gallery_failures'].append({
            'ubigeo': district,
            'district': metadata['name'],
            'error': str(error),
        })
        print(
            'GALLERY_ERROR', district, type(error).__name__, str(error),
            flush=True,
        )
        raise
    finally:
        write_report(report)


def capture_formalization_details(district, report):
    metadata = DISTRICTS[district]
    lots = cofopri_vector_migration.merged_formalization_lots(district)
    print(
        'FORMAL_START', district, metadata['name'], len(lots),
        flush=True,
    )
    started = time.monotonic()
    saved = failed = skipped = 0
    for index, lot in enumerate(lots, 1):
        properties = lot.get('properties') or {}
        predio = str(properties.get('ID_PREDIO_RPU') or lot.get('id') or '')
        object_id = properties.get('OBJECTID')
        if (not predio.startswith('P')
                or type(object_id) is not int or object_id <= 0):
            skipped += 1
            continue
        try:
            value = vector_snapshots.formalization_detail(
                lot['source'], predio, object_id, district)
            if value.get('FORMALIZATION_DETAIL_STATUS') == 'available':
                saved += 1
            else:
                failed += 1
                report['formalization_detail_failures'].append({
                    'ubigeo': district,
                    'source': lot['source'],
                    'predio': predio,
                    'object_id': object_id,
                    'error': 'No devolvió datos',
                })
        except Exception as error:
            failed += 1
            report['formalization_detail_failures'].append({
                'ubigeo': district,
                'source': lot['source'],
                'predio': predio,
                'object_id': object_id,
                'error': str(error),
            })
        if index % 100 == 0:
            print(
                'FORMAL_PROGRESS', district, index, len(lots),
                'saved', saved, 'failed', failed, 'skipped', skipped,
                flush=True,
            )
            write_report(report)
    item = {
        'ubigeo': district,
        'district': metadata['name'],
        'available': len(lots),
        'saved': saved,
        'failed': failed,
        'skipped': skipped,
        'seconds': round(time.monotonic() - started, 1),
    }
    report['formalization_results'].append(item)
    try:
        imported = migrate_formalization_details(
            Gateway(), district, metadata['name'], lots,
            actor='carga-completa-catastro-maestro')
        item['d1_import'] = {
            'available': imported.get('available', 0),
            'processed': imported.get('processed', 0),
        }
    except Exception as error:
        item['d1_import_error'] = str(error)
    write_report(report)
    print('FORMAL_DONE', district, json.dumps(item), flush=True)


def main():
    report = {
        'started_at': int(time.time()),
        'gallery_results': [],
        'gallery_failures': [],
        'formalization_results': [],
        'formalization_detail_failures': [],
    }
    for district in pcdpi_districts():
        capture_gallery_district(district, report)
    for district in sorted(DISTRICTS):
        capture_formalization_details(district, report)
    report['finished_at'] = int(time.time())
    write_report(report)
    print(
        'FINAL',
        json.dumps({
            'gallery_districts': len(report['gallery_results']),
            'gallery_failures': len(report['gallery_failures']),
            'formalization_districts': len(report['formalization_results']),
            'formalization_detail_failures':
                len(report['formalization_detail_failures']),
        }),
        flush=True,
    )
    return 0 if not report['gallery_failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
