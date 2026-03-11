from requerimientos.models import Requerimiento
print("Total de requerimientos:", Requerimiento.objects.count())
for r in Requerimiento.objects.all()[:5]:
    print(f"ID: {r.id}")
    print(f"  Fuente: {r.fuente}")
    print(f"  Agente: {r.agente}")
    print(f"  Requerimiento: {r.requerimiento[:100] if r.requerimiento else 'VACÍO'}")
    print(f"  Agente tel: {r.agente_telefono}")
    print(f"  Características extra: {r.caracteristicas_extra}")
    print(f"  Piso preferencia: {r.piso_preferencia}")
    print()