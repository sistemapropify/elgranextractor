"""Import every archived COFOPRI vector layer into the D1 master."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from django.conf import settings

if not settings.configured:
    settings.configure(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    })

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp'))

from catastro import cofopri_vector_migration, vector_snapshots
from catastro.master_d1 import Gateway
from catastro.storage import R2
from cuadrantizacion.geollaqta import DISTRICTS

OUTPUT = Path(r'D:\PROMETEO\catastro_completo\vectores_d1_resultado.json')


def run_layer(gateway, cloud, ubigeo, source, layer):
    result = cofopri_vector_migration.migrate_snapshot_direct(
        gateway,
        ubigeo,
        DISTRICTS[ubigeo]['name'],
        source=source,
        layer=layer,
        batch_size=100,
        actor='carga-completa-catastro-maestro',
        cloud=cloud,
        progress=lambda item: print(
            'PROGRESS', ubigeo, source, layer,
            item['processed'], item['total'], item['remaining'],
            flush=True,
        ),
    )
    print(
        'DONE', ubigeo, source, layer,
        result['available'], result['processed'],
        flush=True,
    )
    return result


def main():
    gateway = Gateway()
    cloud = R2(timeout=30)
    inventory = vector_snapshots.inventory(cloud=cloud)['snapshots']
    available = {
        (row['ubigeo'], row.get('source') or 'pcdpi', row['layer'])
        for row in inventory
    }
    results = []
    failures = []
    jobs = []
    for ubigeo, source, layer in sorted(available):
        if layer == 'lotes' and source in ('wgs84', 'psad56'):
            # The merged formalization lot importer already produced these.
            continue
        jobs.append((ubigeo, source, layer))
    print('TOTAL_LAYERS', len(jobs), flush=True)
    for index, (ubigeo, source, layer) in enumerate(jobs, 1):
        started = time.monotonic()
        print(
            'START', index, len(jobs), ubigeo, source, layer,
            flush=True,
        )
        try:
            result = run_layer(gateway, cloud, ubigeo, source, layer)
            results.append({
                **result,
                'seconds': round(time.monotonic() - started, 1),
            })
        except Exception as error:
            failures.append({
                'ubigeo': ubigeo,
                'source': source,
                'layer': layer,
                'error': str(error),
            })
            print(
                'ERROR', ubigeo, source, layer,
                type(error).__name__, str(error),
                flush=True,
            )
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
            'completed_layers': len(results),
            'failures': len(failures),
        }),
        flush=True,
    )
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
