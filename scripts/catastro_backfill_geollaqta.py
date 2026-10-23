"""Resume the durable Geollaqta-to-master backfill from existing R2 manifests."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp'))

from catastro.geollaqta_bulk import backfill  # noqa: E402
from catastro.master_d1 import D1Store  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ubigeo', default='040126')
    parser.add_argument('--batch-size', type=int, default=50)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.dry_run:
        from catastro.geollaqta_bulk import lot_ids
        ids, truncated = lot_ids(args.ubigeo)
        print(json.dumps({'ubigeo': args.ubigeo, 'lots': len(ids),
                          'truncated': truncated, 'first': ids[:5],
                          'last': ids[-5:]}, ensure_ascii=False))
        return
    store = D1Store(scope=args.ubigeo)
    result = backfill(store, args.ubigeo, args.batch_size, args.start,
                      args.count, 'sistema-geollaqta', not args.dry_run)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
