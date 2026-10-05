"""Local window alternative. Read-only preview; no production DB or cookies.

Run from webapp: python -m scrapi.adondevivir_local
The person interacts directly with the browser window. No CAPTCHA automation.
"""
import argparse
import json
import os

from .contracts import ScrapingInterrupted
from .source_config import DEFAULT_URLS, validate_url


def main(argv=None):
    parser = argparse.ArgumentParser(description='Adondevivir: ventana real en Windows, sin dashboard ni BD.')
    parser.add_argument('--url', default=DEFAULT_URLS['adondevivir'])
    parser.add_argument('--max-pages', type=int, default=1)
    args = parser.parse_args(argv)
    if os.name != 'nt':
        parser.error('Esta alternativa requiere Windows con una sesión de escritorio abierta.')
    if not 1 <= args.max_pages <= 300:
        parser.error('--max-pages debe estar entre 1 y 300.')
    try:
        url = validate_url('adondevivir', args.url)
    except ValueError as exc:
        parser.error(str(exc))
    from .paged_engine import run_paged
    print('Abriendo una ventana real. Haz la verificación allí cuando el portal la solicite. '
          'Esta prueba no guarda en la base de datos ni mueve cookies.', flush=True)
    def progress(payload):
        if payload.get('message'):
            print(payload['message'], flush=True)
        return True
    try:
        rows = run_paged('adondevivir', source_url=url, max_paginas=args.max_pages,
                         listing_only=True, native_verification=True, progress_callback=progress)
    except (ScrapingInterrupted, RuntimeError) as exc:
        print(f'No se confirmó la lectura: {exc}', flush=True)
        return 1
    print(json.dumps({'anuncios': len(rows), 'recorrido': rows.discovery.as_dict(),
                      'muestra': list(rows[:3]), 'guardado_en_bd': False}, ensure_ascii=False, default=str), flush=True)
    return 0 if rows else 1


if __name__ == '__main__':
    raise SystemExit(main())
