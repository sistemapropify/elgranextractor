import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from requerimientos.models import Requerimiento
print("Total de requerimientos:", Requerimiento.objects.count())
# Últimos 5 registros (los más recientes)
for r in Requerimiento.objects.order_by('-id')[:5]:
    print(f"ID: {r.id}")
    print(f"  Fuente: {r.fuente}")
    print(f"  Agente: {r.agente}")
    req = r.requerimiento
    if req:
        # Limitar a 100 caracteres y reemplazar caracteres problemáticos
        try:
            print(f"  Requerimiento: {req[:100]}")
        except UnicodeEncodeError:
            print(f"  Requerimiento: (contenido con caracteres especiales)")
    else:
        print(f"  Requerimiento: VACÍO")
    print(f"  Agente tel: {r.agente_telefono}")
    print(f"  Características extra: {r.caracteristicas_extra}")
    print(f"  Piso preferencia: {r.piso_preferencia}")
    print()