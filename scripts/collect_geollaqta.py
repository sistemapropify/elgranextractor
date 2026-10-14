"""CLI for the same collector invoked by the Catastro dashboard and skill."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from catastro.jobs import run_job, start_job


def main():
    parser = argparse.ArgumentParser(description='Archivar lotes de Geollaqta en R2, con reanudación.')
    parser.add_argument('--ubigeo', default='040126', help='Distrito; Yanahuara por defecto.')
    parser.add_argument('--limit', type=int, default=10, help='Entre 1 y 500 lotes por ejecución.')
    parser.add_argument('--lot', help='Código catastral de un lote individual.')
    parser.add_argument('--retry-missing', action='store_true', help='Volver a consultar documentos pendientes.')
    parser.add_argument('--job-id', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        job_id = args.job_id or start_job(args.ubigeo, args.limit, args.lot, args.retry_missing, launch=False)
        print(json.dumps({'job_id': job_id, 'result': run_job(job_id)}, ensure_ascii=False))
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
