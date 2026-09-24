"""ACM experimental por componentes. Sin escrituras ni dependencias de ML."""
import math
from statistics import median

VERSION = 'componentes-1'
MIN_LANDS = 1
MIN_HOUSES = 1
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
    target = kind(data.get('property_type', 'Casa'))
    if target not in ('Casa','Terreno','Departamento','Oficina'):
        raise ValueError('Tipo de propiedad inválido')
    output = {'property_type':target}
    for key, low, high in [('lat',-90,90), ('lng',-180,180), ('radius',100,2000),
                           ('max_radius',100,5000), ('land',.01,1000000), ('built',.01,1000000)]:
        optional = (key=='built' and target=='Terreno') or (key=='land' and target in ('Departamento','Oficina'))
        value = number(data.get(key))
        if optional and value in (None,0):
            output[key] = 0
            continue
        if value is None or not low <= value <= high:
            raise ValueError(f'{key}: valor inválido (entre {low} y {high}).')
        output[key] = value
    if output['max_radius'] < output['radius']:
        raise ValueError('El límite de terrenos no puede ser menor que el radio de casas.')
    sources = data.get('sources')
    if not isinstance(sources, list) or not sources or any(s not in SOURCES for s in sources):
        raise ValueError('Selecciona al menos una fuente válida.')
    output['sources'] = sorted(set(sources))
    for key in ('rooms','baths','floor'):
        raw=data.get(key)
        value=number(raw)
        applicable=target!='Terreno' and (key!='rooms' or target!='Oficina') and (key!='floor' or target!='Casa')
        if not applicable or raw in (None,''):
            output[key]=None
        elif value is None or not 0<=value<=200 or (key!='baths' and value!=int(value)):
            raise ValueError(f'{key}: valor inválido')
        else: output[key]=value
    return output


def kind(value):
    text = str(value or '').strip().casefold()
    if text in ('casa', 'house', 'casas'): return 'Casa'
    if text in ('terreno', 'land', 'lote', 'terrenos', 'lot'): return 'Terreno'
    if text in ('departamento','apartment','apartamento','flat','duplex'): return 'Departamento'
    if text in ('oficina','office'): return 'Oficina'
    return None


def reason(record, p):
    issues = []
    if not positive(record.get('price')): issues.append('Precio sin informar o inválido')
    if record['kind'] in ('Casa','Terreno') and not positive(record.get('land')): issues.append('Falta área de terreno')
    if record['kind'] != 'Terreno' and not positive(record.get('built')):
        issues.append('Falta área construida')
    if record.get('precision') != 'exacta': issues.append('Ubicación no exacta')
    if record.get('state') != 'activa': issues.append('Disponibilidad sin confirmar')
    if record.get('operation') != 'Venta': issues.append('Operación de venta sin confirmar')
    if record.get('review_excluded'): issues.append('Excluida por revisión de calidad')
    if record['kind'] == 'Terreno' and positive(record.get('built')):
        issues.append('Terreno con construcción: revisar antes de usar como suelo')
    if record['kind'] in ('Casa','Terreno') and positive(record.get('land')) and not .5 <= record['land']/p['land'] <= 2:
        issues.append('Terreno fuera del rango de tamaño comparable (0,5 a 2 veces)')
    if record['kind'] != 'Terreno' and positive(record.get('built')) and not .5 <= record['built']/p['built'] <= 2:
        issues.append('Construcción fuera del rango de tamaño comparable (0,5 a 2 veces)')
    # Rooms, bathrooms and floor remain descriptive until the model can assign
    # an economic adjustment to their differences. Exact matching here would
    # discard otherwise comparable properties and bias small samples to zero.
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
        if field == 'land' and a['kind'] in ('Departamento','Oficina') and av is None and bv is None: continue
        if av is None or bv is None or abs(av/bv-1) > (.03 if field=='price' else .01): return False
    return True


def candidates(records, p):
    result = []
    for source in records:
        row = dict(source)
        row['kind'] = kind(row.get('kind'))
        if not row['kind']: continue
        target=p.get('property_type','Casa')
        if row['kind'] not in ({'Casa','Terreno'} if target=='Casa' else {target}): continue
        for key in ('lat', 'lng', 'price', 'land', 'built','rooms','baths','floor'): row[key] = number(row.get(key))
        if row['lat'] is None or row['lng'] is None or not -90<=row['lat']<=90 or not -180<=row['lng']<=180:
            continue
        row['distance'] = round(distance(p['lat'],p['lng'],row['lat'],row['lng']),2)
        if row['distance'] > (p['max_radius'] if target=='Casa' and row['kind']=='Terreno' else p['radius']): continue
        # La similitud se calcula para cada registro, incluidos los que quedan
        # como referencia, para que el agente pueda encontrarlos en el mapa y
        # decidir con evidencia si conviene incluirlos.
        row.update(_similarity_metrics(row, p))
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
    if p.get('property_type','Casa')!='Casa':
        return calculate_same_type(records,p,excluded)
    excluded=set(excluded)
    houses=[r for r in records if r['kind']=='Casa' and not r['issues'] and r['id'] not in excluded]
    eligible_lands=[r for r in records if r['kind']=='Terreno' and not r['issues'] and r['id'] not in excluded]
    radius=p['radius']
    while radius < p['max_radius'] and not any(r['distance']<=radius for r in eligible_lands):
        radius=min(radius+500,p['max_radius'])
    lands=[r for r in eligible_lands if r['distance']<=radius]
    result={'version':VERSION,'model':'components','property_type':'Casa','status':'insufficient','messages':[], 'land_radius':radius,
            'land_count':len(lands),'house_count':len(houses),'min_lands':MIN_LANDS,'min_houses':MIN_HOUSES,
            'land_ids':[r['id'] for r in lands], 'house_ids':[r['id'] for r in houses],
            'old':old_estimate(houses,p['built']), 'new':None,'breakdown':[], 'land_unit':None}
    if len(lands)<MIN_LANDS:
        result['messages'].append('No hay terrenos válidos seleccionados para obtener una referencia de suelo. No se puede deducir ese precio de las áreas de las casas.')
        return result
    if len(lands)<5:
        result['messages'].append(f'Muestra reducida: referencia de suelo calculada con {len(lands)} terrenos válidos. Revisa su comparabilidad.')
    units=sorted(r['price']/r['land'] for r in lands)
    unit=median(units)
    q25=units[int((len(units)-1)*.25)];q75=units[int((len(units)-1)*.75)]
    result['land_unit']=unit
    result['land_dispersion']=(q75-q25)/unit
    if result['land_dispersion']>1:
        result['messages'].append('Precios de suelo muy dispersos: se muestra el cálculo orientativo con la mediana; revisa los terrenos seleccionados.')
    residuals=[]
    usable_rows=[]
    for row in houses:
        land_value=row['land']*unit
        remainder=row['price']-land_value
        result['breakdown'].append({'id':row['id'],'price':row['price'],'land_unit':unit,'land_value':land_value,
            'remainder':remainder,'built_unit':remainder/row['built'],'usable':remainder>0,
            'target_estimate':p['land']*unit+p['built']*(remainder/row['built']),
            'similarity_score':_comparability_gap(row,p), **_similarity_metrics(row,p)})
        if remainder>0:
            built_unit=remainder/row['built']
            residuals.append(built_unit)
            usable_rows.append((row,built_unit))
    invalid=len(houses)-len(residuals)
    result['usable_house_count']=len(residuals)
    if invalid:
        result['messages'].append(f'{invalid} casas tienen remanente no positivo: quedan visibles para revisión y no intervienen en la mediana de construcción y mejoras.')
    if len(residuals)<MIN_HOUSES:
        result['messages'].append('Se calculó el suelo y el desglose disponible, pero no hay casas seleccionadas con remanente positivo para estimar construcción y mejoras.')
        return result
    weight_rows=[]
    for row,built_value in usable_rows:
        similarity=_similarity_metrics(row,p)['overall_similarity']/100
        weight=max(.01,similarity)**2
        weight_rows.append((row,built_value,weight))
    weight_total=sum(item[2] for item in weight_rows)
    weight_rows.sort(key=lambda item:item[0]['id'])
    recommended_row=min(weight_rows,key=lambda item:_comparability_gap(item[0],p))[0]
    for row,built_value,weight in weight_rows:
        detail=next(item for item in result['breakdown'] if item['id']==row['id'])
        detail['similarity_weight']=100*weight/weight_total if weight_total else 0
        detail['recommended']=row['id']==recommended_row['id']
    if len(residuals)<3:
        result['messages'].append(f'Muestra reducida: aporte de construcción estimado con {len(residuals)} casa(s). Resultado orientativo.')
    residuals.sort()
    built_unit=median(residuals)
    built_unit_method='median'
    built_reference_id=None
    result.update(built_unit_min=residuals[0], built_unit_max=residuals[-1],
                  built_unit_dispersion=(residuals[-1]-residuals[0])/built_unit)
    dispersion_ratio=residuals[-1]/residuals[0] if residuals[0] > 0 else float('inf')
    if dispersion_ratio > 2.5:
        if len(usable_rows)==2:
            chosen_row,built_unit=min(usable_rows,key=lambda item:_comparability_gap(item[0],p))
            built_unit_method='closest_comparable'
            built_reference_id=chosen_row['id']
            selected_weight=next(item[2] for item in weight_rows if item[0]['id']==chosen_row['id'])/weight_total*100 if weight_total else 0
            result['messages'].append(
                f'Los dos aportes de construcción están muy dispersos '
                f'({_unit_message(residuals[0])} a {_unit_message(residuals[-1])}). '
                f'Como solo hay dos casas, se usa el comparable más parecido '
                f'({_unit_message(built_unit)}; peso de similitud {selected_weight:.0f}%) y el otro queda como referencia; no se promedian extremos.'
            )
        else:
            built_unit,built_reference_row=_weighted_median(weight_rows)
            built_unit_method='weighted_median'
            built_reference_id=built_reference_row['id']
            result['messages'].append(
                f'El aporte observado de construcción y mejoras está muy disperso '
                f'({_unit_message(residuals[0])} a {_unit_message(residuals[-1])}). '
                f'Se usa una mediana ponderada por similitud ({_unit_message(built_unit)}); '
                f'las superficies más parecidas tienen mayor peso y el resultado requiere revisión.'
            )
    land_value=p['land']*unit
    total=land_value+p['built']*built_unit
    # Spread of adjusted comparables, not a calibrated confidence interval.
    estimates=sorted(land_value+p['built']*r for r in residuals)
    result.update(status='ok',built_unit_method=built_unit_method,built_reference_id=built_reference_id,
        recommended_ids=[recommended_row['id']],
        new={'total':total,'land_value':land_value,'built_value':p['built']*built_unit,
        'built_unit':built_unit, 'range_low':estimates[int((len(estimates)-1)*.25)],
        'range_high':estimates[math.ceil((len(estimates)-1)*.75)],
        'delta':total-result['old']['total'], 'delta_pct':100*(total/result['old']['total']-1)})
    return result


def _unit_message(value):
    return f'USD {value:,.0f}/m²'


def _comparability_gap(row,p):
    """Distancia normalizada (0 es idéntico) de superficies y ubicación."""
    return 1-(_similarity_metrics(row,p)['overall_similarity']/100)


def _similarity_metrics(row,p):
    """Porcentajes explicables para el agente: terreno, construcción y distancia."""
    def area_similarity(value,target):
        if not positive(value) or not positive(target): return 0
        return max(0,100*(1-abs(value-target)/target))
    land=area_similarity(row.get('land'),p.get('land'))
    built=area_similarity(row.get('built'),p.get('built'))
    radius=max(p.get('radius') or 1,1)
    distance=max(0,100*(1-min((row.get('distance') or 0)/radius,1)))
    return {'land_similarity':round(land,1),'built_similarity':round(built,1),
            'distance_similarity':round(distance,1),'overall_similarity':round(land*.45+built*.45+distance*.10,1)}


def _weighted_median(weight_rows):
    """Devuelve el valor central acumulando pesos, sin promediar extremos."""
    ordered=sorted(weight_rows,key=lambda item:item[1])
    total=sum(item[2] for item in ordered)
    accumulated=0
    for row,built_value,weight in ordered:
        accumulated+=weight
        if accumulated>=total/2:
            return built_value,row
    return ordered[-1][1],ordered[-1][0]


def calculate_same_type(records,p,excluded=()):
    target=p['property_type'];is_land=target=='Terreno';area='land' if is_land else 'built'
    rows=[r for r in records if r['kind']==target and not r['issues'] and r['id'] not in set(excluded) and r['distance']<=p['radius']]
    units=sorted(r['price']/r[area] for r in rows)
    result={'version':VERSION,'model':'land' if is_land else 'built','property_type':target,
        'status':'insufficient','messages':[],'land_radius':p['radius'],'land_count':len(rows) if is_land else 0,
        'house_count':0 if is_land else len(rows),'land_ids':[r['id'] for r in rows] if is_land else [],
        'house_ids':[] if is_land else [r['id'] for r in rows], 'min_lands':MIN_LANDS,'min_houses':MIN_HOUSES,
        'new':None,'old':None,'land_unit':None,'breakdown':[]}
    if rows:
        weights=[1/((r['distance'] or 1)+1) for r in rows]
        old_unit=sum(w*r['price']/r[area] for w,r in zip(weights,rows))/sum(weights)
        result['old']={'total':old_unit*p[area],'unit':old_unit,'houses':len(rows)}
    for r in rows:
        result['breakdown'].append({'id':r['id'],'method':result['model'],'offer_unit':r['price']/r[area],
            'area':r[area],'adjusted_total':r['price']/r[area]*p[area],'usable':True})
    minimum=1
    if len(rows)<minimum:
        result['messages']=[f'Faltan comparables completos de {target.lower()}: {len(rows)} de {minimum} requeridos.']
        return result
    if len(rows)<5:
        result['messages'].append(f'Muestra reducida: cálculo con {len(rows)} comparables completos.')
    unit=median(units);q25=units[int((len(units)-1)*.25)];q75=units[int((len(units)-1)*.75)]
    if (q75-q25)/unit>1:
        result['messages'].append('Precios muy dispersos: cálculo orientativo con la mediana; revisa los comparables seleccionados.')
    total=unit*p[area]
    if is_land:result.update(land_unit=unit,land_dispersion=(q75-q25)/unit)
    result.update(status='ok',new={'total':total,'unit':unit,'area_basis':area,
        'range_low':q25*p[area],'range_high':units[math.ceil((len(units)-1)*.75)]*p[area],
        'delta':total-result['old']['total'],'delta_pct':100*(total/result['old']['total']-1)})
    return result
