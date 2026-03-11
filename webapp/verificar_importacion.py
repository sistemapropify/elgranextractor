#!/usr/bin/env python
"""
Verifica que los requerimientos se hayan importado correctamente.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento

def main():
    total = Requerimiento.objects.count()
    print(f"Total requerimientos en base de datos: {total}")
    
    if total > 0:
        print("\nÚltimos 5 requerimientos:")
        for r in Requerimiento.objects.order_by('-id')[:5]:
            print(f"  ID: {r.id}")
            print(f"    Fuente: {r.fuente}")
            print(f"    Fecha: {r.fecha}")
            print(f"    Agente: {r.agente[:30]}")
            print(f"    Tipo: {r.tipo_propiedad}")
            print(f"    Distritos: {r.distritos[:40]}")
            print(f"    Presupuesto: {r.presupuesto_monto} {r.presupuesto_moneda}")
            print()
    
    # Verificar conteo por fuente
    print("\nConteo por fuente:")
    from django.db.models import Count
    for fuente, count in Requerimiento.objects.values_list('fuente').annotate(total=Count('id')).order_by('-total'):
        print(f"  {fuente}: {count}")
    
    # Verificar que haya al menos 552 registros (los que importamos)
    if total >= 552:
        print(f"\n✅ Importación exitosa: se importaron {total} registros (esperados al menos 552).")
    else:
        print(f"\n⚠️  Advertencia: solo hay {total} registros, se esperaban 552.")

if __name__ == '__main__':
    main()