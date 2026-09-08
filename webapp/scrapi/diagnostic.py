"""Read-only listing probe. No Django setup, property writes, details or uploads.

python -m scrapi.diagnostic urbania --start-page 5 --max-pages 8 --output probe.json
"""
import argparse
import json
from pathlib import Path
from .paged_engine import run_paged
from .source_config import DEFAULT_URLS, source_snapshot
from .telemetry import sanitize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('portal', choices=list(DEFAULT_URLS))
    parser.add_argument('--url')
    parser.add_argument('--start-page', type=int, default=1)
    parser.add_argument('--max-pages', type=int, default=1, help='Absolute last page allowed; a limit is partial coverage')
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-items', type=int, default=120)
    args = parser.parse_args()
    config = source_snapshot(args.portal, args.url)
    events = []
    def progress(payload):
        event = sanitize({k: v for k, v in payload.items() if k != 'candidate_batch'})
        events.append(event)
        print(json.dumps(event, ensure_ascii=False), flush=True)
        return True
    result = {'mode': 'listing_only', 'source': config, 'start_page': args.start_page}
    try:
        if args.portal == 'facebook_marketplace':
            from .facebook_marketplace_scraper import run_scraper
            rows = run_scraper(search_url=config['source_url'], max_items=args.max_items,
                               discovery_only=True, progress_callback=progress)
        else:
            rows = run_paged(args.portal, source_url=config['source_url'], start_page=args.start_page,
                             max_paginas=args.max_pages, listing_only=True, progress_callback=progress)
        result.update(discovery=rows.discovery.as_dict(), rows=list(rows))
    except Exception as exc:
        result.update(error=str(exc), discovery={'complete': False, 'stop_reason': 'failed'})
        raise
    finally:
        result['events'] = events
        result['rows'] = [sanitize(row) for row in result.get('rows', [])]
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
