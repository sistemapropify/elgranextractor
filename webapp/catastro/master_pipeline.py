"""Explicit collection hold until the new end-to-end pipeline is accepted."""
import os

def status():
    # Deliberately not enabled by implementing a normalizer or writing a plan.
    # Durable sink and operational acceptance are still separate requirements.
    durable=os.environ.get('CATASTRO_MASTER_STORAGE')=='d1'
    blockers=['La nueva extracción permanece detenida por indicación del usuario.',
              'Pendiente validar el recorrido completo con un piloto autorizado.']
    if not durable:blockers.insert(1,'Este proceso no tiene seleccionada la conexión D1 del maestro.')
    return {'schema': 'catastro-maestro-v1', 'collection_enabled': False,
            'historical_migration_enabled': False,
            'tabular_backend':'d1' if durable else 'memory',
            'normalization_available': True,
            'blockers': blockers}


def require_collection_ready():
    raise ValueError('Extracción detenida: el nuevo Catastro Maestro debe validarse antes de reiniciar COFOPRI.')
