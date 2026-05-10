import os
import django
from django.db import transaction

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from requerimientos.models import Requerimiento

print('Borrando todos los registros de Requerimiento...')

def borrar_todos_requerimientos():
    total_eliminados = 0
    batch_size = 500
    
    while True:
        # Obtener un lote de registros para eliminar
        requerimientos = list(Requerimiento.objects.all()[:batch_size])
        
        if not requerimientos:
            break
        
        # Eliminar el lote
        ids = [r.id for r in requerimientos]
        count = Requerimiento.objects.filter(id__in=ids).delete()[0]
        total_eliminados += count
        
        print(f'Eliminados {count} registros. Total: {total_eliminados}')
    
    print(f'Total de registros eliminados: {total_eliminados}')

if __name__ == '__main__':
    borrar_todos_requerimientos()
