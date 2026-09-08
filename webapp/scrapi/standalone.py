"""Legacy script entry points use the same traversal as the dashboard."""
import json
from datetime import datetime
from pathlib import Path
from openpyxl import Workbook
from .paged_engine import run_paged
from .source_config import source_snapshot


def export_portal(portal):
    config = source_snapshot(portal)
    rows = []
    target = Path(f'{portal}_{datetime.now():%Y%m%d_%H%M%S}.xlsx')
    def save(batch):
        rows.extend(batch)
        return {'total': len(rows), 'errores': 0}
    try:
        result = run_paged(portal, source_url=config['source_url'], batch_callback=save)
        print(json.dumps(result.discovery.as_dict(), ensure_ascii=False))
    finally:
        if rows:
            book = Workbook()
            sheet = book.active
            columns = [k for k in rows[0] if k != 'datos_crudos']
            sheet.append(columns)
            for row in rows:
                sheet.append([row.get(k) for k in columns])
            book.save(target)
            print(f'{len(rows)} filas conservadas en {target}')
