"""ACM experimental por componentes. Sin escrituras ni dependencias de ML."""
import math
from statistics import median

VERSION = 'componentes-1'
MIN_LANDS = 5
MIN_HOUSES = 3
SOURCES = ('propify', 'remax', 'properati', 'adondevivir', 'urbania', 'facebook_marketplace')


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def positive(value):
    value = number(value)
    return value if value is not None and value > 0 else None


def distance(a, b, c, d):
    a, b, c, d = map(math.radians, (a, b, c, d))
    v = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(max(0, v))))


def parameters(data):
    output = {}
    for key, low, high in [('lat',-90,90), ('lng',-180,180), ('radius',100,2000),
                           ('max_radius',100,5000), ('land',.01,1000000), ('built',.01,1000000)]:
        value = number(data.get(key))
        if value is None or not low <= value <= high:
            raise ValueError(f'{key}: valor inválido (entre {low} y {high}).')
        output[key] = value
    if output['max_radius'] < output['radius']:
        raise ValueError('El límite de terrenos no puede ser menor que el radio de casas.')
    sources = data.get('sources')
    if not isinstance(sources, list) or not sources or any(s not in SOURCES for s in sources):
        raise ValueError('Selecciona al menos una fuente válida.')
    output['sources'] = sorted(set(sources))
    return output


def kind(value):
    text = str(value or '').strip().casefold()
    if text in ('casa', 'house', 'casas'): return 'Casa'
    if text in ('terreno', 'land', 'lote', 'terrenos', 'lot'): return 'Terreno'
    return None


def reason(record, p):
    issues = []
    if not positive(record.get('price')): issues.append('Precio sin informar o inválido')
    if not positive(record.get('land')): issues.append('Falta área de terreno')
    if record['kind'] == 'Casa' and not positive(record.get('built')):
        issues.append('Falta área construida')
    if record.get('precision') != 'exacta': issues.append('Ubicación no exacta')
    if record.get('state') != 'activa': issues.append('Disponibilidad sin confirmar')
    if record.get('operation') != 'Venta': issues.append('Operación de venta sin confirmar')
    if record.get('review_excluded'): issues.append('Excluida por revisión de calidad')
    if record['kind'] == 'Terreno' and positive(record.get('built')):
        issues.append('Terreno con construcción: revisar antes de usar como suelo')
    if positive(record.get('land')) and not .5 <= record['land']/p['land'] <= 2:
        issues.append('Terreno fuera del rango de tamaño comparable (0,5 a 2 veces)')
    if record['kind'] == 'Casa' and positive(record.get('built')) and not .5 <= record['built']/p['built'] <= 2:
        issues.append('Construcción fuera del rango de tamaño comparable (0,5 a 2 veces)')
    return issues


def same_listing(a, b):
    if a.get('url') and a['url'].rstrip('/') == str(b.get('url') or '').rstrip('/'):
        return True
    if a['kind'] != b['kind'] or a.get('precision') != 'exacta' or b.get('precision') != 'exacta':
        return False
    if a['source'] == b['source']: return False
    if distance(a['lat'],a['lng'],b['lat'],b['lng']) > 15: return False
    for field in ('price', 'land', 'built'):
        av, bv = positive(a.get(field)), positive(b.get(field))
        if field == 'built' and a['kind'] == 'Terreno' and av is None and bv is None: continue
        if av is None or bv is None or abs(av/bv-1) > (.03 if field=='price' else .01): return False
    return True


def candidates(records, p):
    result = []
    for source in records:
        row = dict(source)
        row['kind'] = kind(row.get('kind'))
        if not row['kind']: continue
        for key in ('lat', 'lng', 'price', 'land', 'built'): row[key] = number(row.get(key))
        if row['lat'] is None or row['lng'] is None or not -90<=row['lat']<=90 or not -180<=row['lng']<=180:
            continue
        row['distance'] = round(distance(p['lat'],p['lng'],row['lat'],row['lng']),2)
        if row['distance'] > (p['radius'] if row['kind']=='Casa' else p['max_radius']): continue
        row['issues'] = reason(row,p)
        row['duplicate_of'] = None
        result.append(row)
    # Prefer usable records, then Propify. Keep duplicate candidates visible as references.
    result.sort(key=lambda r:(len(r['issues']), r['source']!='propify', r['distance'],r['id']))
    representatives = []
    for row in result:
        match = next((r for r in representatives if same_listing(row,r)),None)
        if match:
            row['duplicate_of'] = match['id']
            row['issues'].append(f"Posible duplicado de {match['id']}; revisar fuentes")
        else: representatives.append(row)
    houses = [r for r in result if r['kind']=='Casa']
    for row in result:
        if row['kind'] != 'Terreno' or row['issues']: continue
        for house in houses:
            if (house.get('precision')=='exacta' and positive(house.get('land')) and positive(house.get('price'))
                and abs(row['land']/house['land']-1)<.01 and abs(row['price']/house['price']-1)<.03
                and distance(row['lat'],row['lng'],house['lat'],house['lng'])<30):
                row['issues'].append('Posible casa anunciada también como terreno')
                break
    return sorted(result,key=lambda r:(r['kind'],r['distance'],r['id']))


def old_estimate(houses, built):
    usable = [r for r in houses if positive(r.get('price')) and positive(r.get('built'))]
    if not usable: return None
    weights = [1/((r['distance'] or 1)+1) for r in usable]
    unit = sum(w*r['price']/r['built'] for w,r in zip(weights,usable))/sum(weights)
    return {'total':unit*built,'unit':unit,'houses':len(usable),
            'formula':'Promedio de precio/m² construido ponderado por 1/(distancia+1) × construcción objetivo'}


def calculate(records, p, excluded=()):
    excluded=set(excluded)
    houses=[r for r in records if r['kind']=='Casa' and not r['issues'] and r['id'] not in excluded]
    eligible_lands=[r for r in records if r['kind']=='Terreno' and not r['issues'] and r['id'] not in excluded]
    radius=p['radius']
    while radius < p['max_radius'] and sum(r['distance']<=radius for r in eligible_lands)<MIN_LANDS:
        radius=min(radius+500,p['max_radius'])
    lands=[r for r in eligible_lands if r['distance']<=radius]
    result={'version':VERSION,'status':'insufficient','messages':[], 'land_radius':radius,
            'land_count':len(lands),'house_count':len(houses),'min_lands':MIN_LANDS,'min_houses':MIN_HOUSES,
            'land_ids':[r['id'] for r in lands], 'house_ids':[r['id'] for r in houses],
            'old':old_estimate(houses,p['built']), 'new':None,'breakdown':[], 'land_unit':None}
    if len(lands)<MIN_LANDS:
        result['messages'].append(f'Suelo sin evidencia suficiente: {len(lands)} de {MIN_LANDS} terrenos requeridos.')
        return result
    units=sorted(r['price']/r['land'] for r in lands)
    unit=median(units)
    q25=units[int((len(units)-1)*.25)];q75=units[int((len(units)-1)*.75)]
    result['land_unit']=unit
    result['land_dispersion']=(q75-q25)/unit
    if result['land_dispersion']>1:
        result['messages'].append('Suelo demasiado heterogéneo: revisa los terrenos seleccionados antes de calcular.')
        return result
    residuals=[]
    for row in houses:
        land_value=row['land']*unit
        remainder=row['price']-land_value
        result['breakdown'].append({'id':row['id'],'price':row['price'],'land_unit':unit,'land_value':land_value,
            'remainder':remainder,'built_unit':remainder/row['built'],'usable':remainder>0})
        if remainder>0: residuals.append(remainder/row['built'])
    invalid=len(houses)-len(residuals)
    if invalid:
        result['messages'].append(f'{invalid} casas tienen remanente no positivo. Desmárcalas o revisa la referencia de suelo; no se han convertido en cero.')
        return result
    if len(residuals)<MIN_HOUSES:
        result['messages'].append(f'Faltan casas completas: {len(residuals)} de {MIN_HOUSES} requeridas.')
        return result
    built_unit=median(residuals)
    land_value=p['land']*unit
    total=land_value+p['built']*built_unit
    # Spread of adjusted comparables, not a calibrated confidence interval.
    estimates=sorted(land_value+p['built']*r for r in residuals)
    result.update(status='ok',new={'total':total,'land_value':land_value,'built_value':p['built']*built_unit,
        'built_unit':built_unit, 'range_low':estimates[int((len(estimates)-1)*.25)],
        'range_high':estimates[math.ceil((len(estimates)-1)*.75)],
        'delta':total-result['old']['total'], 'delta_pct':100*(total/result['old']['total']-1)})
    return result
