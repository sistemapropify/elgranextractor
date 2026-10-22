"""Collection gate controlled by an explicit operator switch."""
import os


def collection_enabled():
    return os.environ.get('CATASTRO_MASTER_COLLECTION_ENABLED') == '1'


def status():
    enabled = collection_enabled()
    durable = os.environ.get('CATASTRO_MASTER_STORAGE') == 'd1'
    blockers = []
    if not enabled:
        blockers = ['La nueva extracción permanece detenida por indicación del usuario.',
                    'Pendiente validar el recorrido completo con un piloto autorizado.']
    if not durable:
        blockers.append('Este proceso no tiene seleccionada la conexión D1 del maestro.')
    return {'schema': 'catastro-maestro-v1', 'collection_enabled': enabled,
            'historical_migration_enabled': False,
            'tabular_backend':'d1' if durable else 'memory',
            'normalization_available': True,
            'blockers': blockers}


def require_collection_ready():
    if not collection_enabled():
        raise ValueError('Extracción detenida: el nuevo Catastro Maestro debe validarse antes de reiniciar COFOPRI.')
