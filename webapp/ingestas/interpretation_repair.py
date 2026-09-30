"""Conservative proposals for legacy extraction defects, without portal access."""
import re
from scrapi.area_evidence import description_areas, numeric_area, text, NUMBER
from scrapi.normalization import listing_operation

VERSION = 'interpretation-20260930'


def propose(row, protected=(), human_verified=False):
    raw = row.get('datos_crudos') or {}
    if not isinstance(raw, dict):
        raw = {}
    # This is an old numeric corruption audit, not a blanket regeneration of
    # valid structured measurements from marketing prose.
    description = raw.get('Descripcion') or raw.get('descripcion') or row.get('descripcion') or ''
    found = description_areas(description)
    changes, reasons, unresolved = {}, [], []
    def change(field, new, evidence):
        old = row.get(field)
        if field in protected or human_verified or new is None or old == new:
            return False
        changes[field] = {'before':old, 'after':new, 'evidence':evidence}
        return True

    land, built = row.get('area_terreno'), row.get('area_construida')
    suspect_land = row.get('tipo_inmueble') == 'Casa' and land is not None and 0 < float(land) < 30
    if suspect_land:
        if found['area_terreno'] and found['area_terreno'] >= 30:
            change('area_terreno',found['area_terreno'],'Superficie de terreno etiquetada en descripción original')
        elif not human_verified:
            unresolved.append('Terreno de casa menor de 30 m² sin total alternativo verificable en el respaldo')
    free_areas = [numeric_area(m) for m in re.findall(rf'({NUMBER})\s*m2\s*libres?\b', text(description))]
    suspect_built = row.get('tipo_inmueble') == 'Casa' and built is not None and (float(built) > 10000 or float(built) in free_areas)
    if suspect_built:
        if found['area_construida'] and found['area_construida'] != built:
            change('area_construida',found['area_construida'],'Superficie construida etiquetada; no superficie libre ni decimal truncado')
        elif not human_verified:
            unresolved.append('Construcción sospechosa sin total alternativo verificable en el respaldo')
    # Only the property URL is admissible here, never the listing search URL.
    url = row.get('url') or raw.get('URL Propiedad') or raw.get('url')
    op = listing_operation({'URL Propiedad': url})
    if op and op != row.get('tipo_operacion'):
        change('tipo_operacion',op,'Operación explícita en la ruta de la publicación individual')
    effective_op = changes.get('tipo_operacion',{}).get('after',row.get('tipo_operacion'))
    price = row.get('precio_usd')
    if effective_op == 'Venta' and row.get('tipo_inmueble') == 'Casa' and price is not None and 0 < float(price) < 1000 and not human_verified:
        unresolved.append('Precio de venta de casa menor de USD 1.000: comprobar si es total, por m² o una cuota')
    if any(key in changes for key in ('area_terreno','area_construida')):
        primary = 'area_terreno' if row.get('tipo_inmueble') == 'Terreno' else 'area_construida'
        area = changes.get(primary,{}).get('after',row.get(primary))
        # Preserve an unrelated legacy area; only update when it followed a
        # component corrected in this same proposal.
        if primary in changes and row.get('area_m2') == row.get(primary):
            change('area_m2',area,'Área principal vinculada a la superficie corregida')
    if protected:
        reasons.append('Campos corregidos manualmente protegidos: '+', '.join(sorted(protected)))
    return {'id':row['id'],'source':row.get('fuente'),'changes':changes,
            'quarantine':unresolved,'notes':reasons,'version':VERSION}
