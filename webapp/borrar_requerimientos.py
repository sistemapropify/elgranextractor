import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento

def main():
    total = Requerimiento.objects.count()
    print(f"Total requerimientos antes de borrar: {total}")
    
    confirmacion = input("¿Estás seguro de borrar TODOS los requerimientos? (escribe 'SI' para confirmar): ")
    if confirmacion.strip().upper() == 'SI':
        Requerimiento.objects.all().delete()
        print(f"Se borraron {total} requerimientos.")
        nuevo_total = Requerimiento.objects.count()
        print(f"Total requerimientos después de borrar: {nuevo_total}")
    else:
        print("Operación cancelada.")

if __name__ == '__main__':
    main()