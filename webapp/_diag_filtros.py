import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import _fetch_properties, _recargar_cache_property_types, _get_property_type_id
from requerimientos.models import Requerimiento

_recargar_cache_property_types()
req = Requerimiento.objects.get(id=24304)
props = _fetch_properties(is_active_only=True)

print(f"Total properties: {len(props)}")
print(f"Requerimiento: tipo={req.tipo_propiedad}, condicion={req.condicion}, distritos={req.distritos}, presupuesto={req.presupuesto_monto} {req.presupuesto_moneda}")
tipo_id = _get_property_type_id(req.tipo_propiedad)
print(f"Tipo id esperado: {tipo_id}")

# Analyze why each casa fails
casa_count = 0
for p in props:
    if p.get('property_type_id') != tipo_id:
        continue
    casa_count += 1
    # Check each filter
    type_ok = p.get('property_type_id') == tipo_id
    
    op_type = p.get('operation_type_id')
    cond = req.condicion.lower().strip()
    cond_ok = True
    if cond == 'compra':
        cond_ok = op_type in (1, 2)
    
    dist_ok = False
    dist_id = p.get('district_id')
    if req.distritos:
        dist_str = str(dist_id)
        for d in req.distritos_lista:
            dl = d.strip().lower()
            if dl == dist_str:
                dist_ok = True
                break
    else:
        dist_ok = True
    
    budget_ok = False
    if req.presupuesto_monto and p.get('price'):
        from decimal import Decimal
        presupuesto = Decimal(str(req.presupuesto_monto))
        precio = Decimal(str(p['price']))
        moneda_req = (req.presupuesto_moneda or 'PEN').upper()
        from matching.engine import _get_moneda_propiedad, _convertir_moneda
        presup_pen = _convertir_moneda(presupuesto, moneda_req, 'PEN')
        precio_pen = _convertir_moneda(precio, _get_moneda_propiedad(p), 'PEN')
        budget_ok = precio_pen <= presup_pen * Decimal('1.10')
    
    print(f"  casa id={p['id']}: district={p['district_id']}({dist_id}), type={type_ok}, cond={cond_ok}, dist={dist_ok}, budget={budget_ok}, price={p['price']}, currency={p.get('currency_id')}, op_type={op_type}")

print(f"\nTotal casas disponibles: {casa_count}")
