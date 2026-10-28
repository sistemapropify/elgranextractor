"""Gallery layer read from the canonical Catastro Maestro dossier."""
from . import master_dossier


def load(lot_id):
    value = master_dossier.load(lot_id, surface='master')
    return {
        'schema': value.get('schema'),
        'lot_id': value.get('lot_id'),
        'master_status': value.get('master_status'),
        'images': value.get('gallery') or [],
        'records': value.get('reports') or [],
        'gallery_page': None,
    }
