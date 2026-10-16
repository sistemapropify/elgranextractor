"""ACM experimental por componentes. Sin escrituras ni dependencias de ML."""
import math
from statistics import median
from .listing_operation import resolve_operation
from .comparable_policy import (age_years, land_only, surface_similarity, selection_metrics,
                               selection_pool, automatic_houses, age_messages)

VERSION = 'componentes-6-antiguedad-grupo-cercano'
MIN_LANDS = 1
MIN_HOUSES = 1
# Portales habilitados en el ACM. La selección se administra aquí, no en el mapa.
SOURCES = ('propify', 'remax', 'properati')


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
    raw_age = data.get('age')
    output['age'] = age_years(raw_age) if target != 'Terreno' else None
    if target != 'Terreno' and raw_age not in (None, '') and output['age'] is None:
        raise ValueError('Antigüedad: ingresa años enteros entre 0 y 150, o déjala vacía.')
    for key, low, high in [('lat',-90,90), ('lng',-180,180), ('radius',100,2000),
                           ('max_radius',100,5000), ('land',.01,1000000), ('built',.01,1000000)]:
        optional = (key=='built' and (target=='Terreno' or land_only(output))) or (key=='land' and target in ('Departamento','Oficina'))
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
    if isinstance(data.get('address'), str):
        output['address'] = data['address'].strip()[:500]
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
    if record.get('operation_status') == 'review': issues.append('Operación contradictoria entre título original y publicación: revisar')
    if record.get('review_excluded'): issues.append('Excluida por revisión de calidad')
    if record['kind'] == 'Terreno' and positive(record.get('built')):
        issues.append('Terreno con construcción: revisar antes de usar como suelo')
    if record['kind'] in ('Casa','Terreno') and positive(record.get('land')) and not .5 <= record['land']/p['land'] <= 2:
        issues.append('Terreno fuera del rango de tamaño comparable (0,5 a 2 veces)')
    if record['kind'] != 'Terreno' and not land_only(p) and positive(record.get('built')) and not .5 <= record['built']/p['built'] <= 2:
        issues.append('Construcción fuera del rango de tamaño comparable (0,5 a 2 veces)')
    if record['kind'] != 'Terreno' and land_only(p):
        issues.append('Casa objetivo de más de 40 años: se valora con terrenos, sin aporte de construcción')
    elif record['kind'] != 'Terreno' and p.get('age') is not None:
        if age_years(record.get('age')) is None or record.get('age_conflict'):
            issues.append('Antigüedad sin informar o con evidencia contradictoria')
        if p.get('property_type', 'Casa') == 'Casa' and (age_years(record.get('age')) or 0) > 40:
            issues.append('Casa de más de 40 años: no aporta referencia de construcción')
        keys = ('land', 'built') if p.get('property_type', 'Casa') == 'Casa' else ('built',)
        for key in keys:
            if positive(record.get(key)) and surface_similarity(record[key], p[key]) < 70:
                issues.append('Superficie con menos de 70% de similitud: revisar antes de valorar')
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
        row['operation'], row['operation_status'] = resolve_operation(row)
        if row['operation'] in ('Alquiler', 'Ambos', 'Anticresis'):
            continue
        row['kind'] = kind(row.get('kind'))
        if not row['kind']: continue
        target=p.get('property_type','Casa')
        if row['kind'] not in ({'Casa','Terreno'} if target=='Casa' else {target}): continue
        for key in ('lat', 'lng', 'price', 'land', 'built','rooms','baths','floor'): row[key] = number(row.get(key))
        row['age'] = age_years(row.get('age'))
        if row['lat'] is None or row['lng'] is None or not -90<=row['lat']<=90 or not -180<=row['lng']<=180:
            continue
        row['distance'] = round(distance(p['lat'],p['lng'],row['lat'],row['lng']),2)
        # Use the same evidence pool for deduplication and land validation at
        # every display radius. Filter visible houses only after these checks.
        if row['distance'] > (p['max_radius'] if target=='Casa' else p['radius']): continue
        # La similitud se calcula para cada registro, incluidos los que quedan
        # como referencia, para que el agente pueda encontrarlos en el mapa y
        # decidir con evidencia si conviene incluirlos.
        row.update(_similarity_metrics(row, p))
        row.update(selection_metrics(row, p))
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
    return sorted((r for r in result if r['kind']=='Terreno' or r['distance']<=p['radius']),
                  key=lambda r:(r['kind'],r['distance'],r['id']))


def old_estimate(houses, built):
    usable = [r for r in houses if positive(r.get('price')) and positive(r.get('built'))]
    if not usable: return None
    weights = [1/((r['distance'] or 1)+1) for r in usable]
    unit = sum(w*r['price']/r['built'] for w,r in zip(weights,usable))/sum(weights)
    return {'total':unit*built,'unit':unit,'houses':len(usable),
            'formula':'Promedio de precio/m² construido ponderado por 1/(distancia+1) × construcción objetivo'}


def calculate(records, p, excluded=()):
    records = [row for row in records if resolve_operation(row)[0] == 'Venta']
    if p.get('property_type','Casa')!='Casa':
        return calculate_same_type(records,p,excluded)
    excluded=set(excluded)
    houses=[r for r in records if r['kind']=='Casa' and not r['issues'] and r['id'] not in excluded]
    eligible_lands=[r for r in records if r['kind']=='Terreno' and not r['issues'] and r['id'] not in excluded]
    # The soil microzone must not expand just because the map radius expands.
    radius=min(500,p['max_radius'])
    while radius < p['max_radius'] and not any(r['distance']<=radius for r in eligible_lands):
        radius=min(radius+500,p['max_radius'])
    lands=[r for r in eligible_lands if r['distance']<=radius]
    if land_only(p) and isinstance(p.get('reference_ids'), list):
        requested = p['reference_ids']
        if 1 <= len(requested) <= 3 and len(set(requested)) == len(requested) and all(i in {r['id'] for r in lands} for i in requested):
            lands=[r for r in lands if r['id'] in requested]
    result={'version':VERSION,'model':'land' if land_only(p) else 'components','property_type':'Casa','status':'insufficient','messages':[], 'land_radius':radius,
            'land_count':len(lands),'house_count':len(houses),'min_lands':MIN_LANDS,'min_houses':MIN_HOUSES,
            'land_ids':[r['id'] for r in lands], 'house_ids':[r['id'] for r in houses],
            'old':old_estimate(houses,p['built']), 'new':None,'breakdown':[], 'land_unit':None}
    if land_only(p):
        result.update(valuation_mode='land_only', house_ids=[], house_count=0)
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
    if land_only(p):
        total = p['land'] * unit
        result.update(model='land', valuation_mode='land_only', house_count=0, house_ids=[],
                      usable_house_count=0, selection_method='nearest',
                      breakdown=[{'id':r['id'], 'method':'land', 'offer_unit':r['price']/r['land'],
                                  'area':r['land'], 'adjusted_total':r['price']/r['land']*p['land'],
                                  'usable':True} for r in lands], status='ok',
                      new={'total':total, 'unit':unit, 'area_basis':'land', 'land_value':total,
                           'built_value':0, 'range_low':q25*p['land'], 'range_high':q75*p['land']})
        result['messages'].append('Casa con más de 40 años: valorada únicamente como terreno según la regla configurada. Construcción sin aporte en este cálculo; no se descuentan gastos de demolición.')
        return result
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
        result['messages'].append(f'{invalid} casas tienen remanente no positivo: quedan visibles para revisión y no intervienen en la estimación de construcción y mejoras.')
    if len(residuals)<MIN_HOUSES:
        result['messages'].append('Se calculó el suelo y el desglose disponible, pero no hay casas seleccionadas con remanente positivo para estimar construcción y mejoras.')
        result['messages'].extend(age_messages(p, []))
        return result
    # Scenario comparisons keep the original evidence and weighting reference.
    weight_params={**p, **p.get('weight_reference', {})}
    # Among suitable houses, keep the nearest reference as the map expands.
    automatic_ids=automatic_houses([row for row,_ in usable_rows], weight_params,
                                   {row['id']:value for row,value in usable_rows})
    reference_ids=p.get('reference_ids') or automatic_ids
    allowed={row['id'] for row,_ in usable_rows}
    if not isinstance(reference_ids,list) or not 1<=len(reference_ids)<=3 or len(set(reference_ids))!=len(reference_ids) or any(i not in allowed for i in reference_ids):
        reference_ids=automatic_ids
    selected_rows=[row for row,_ in usable_rows if row['id'] in reference_ids]
    built_unit=sum(value for row,value in usable_rows if row['id'] in reference_ids)/len(reference_ids)
    weight_rows=[(row,value,1/len(reference_ids) if row['id'] in reference_ids else 0)
                 for row,value in usable_rows]
    residuals.sort()
    built_unit_min=residuals[0]
    built_unit_max=residuals[-1]
    built_unit_method='primary_area_reference'
    built_reference_id=reference_ids[0]
    for row,built_value,weight in weight_rows:
        detail=next(item for item in result['breakdown'] if item['id']==row['id'])
        detail['similarity_weight']=100*weight
        detail['land_adjustment']=(p['land']-row['land'])*unit
        detail['built_adjustment']=(p['built']-row['built'])*built_value
        detail['weighted_contribution']=detail['target_estimate']*weight
        detail['recommended']=row['id'] in reference_ids
        detail['reference_only']=not detail['recommended']
        detail['usable']=detail['recommended']
    result['usable_house_count']=len(reference_ids)
    result['old']=old_estimate(selected_rows,p['built'])
    result['messages'].append(
        f'Se usan {len(reference_ids)} casas aptas. El grupo automático añade hasta tres '
        'casas a no más de 200 m del objetivo, con hasta 50 m de diferencia de distancia '
        'respecto de la primera, superficies similares y aportes coherentes. '
        'Sin antigüedad se prioriza distancia. El suelo se busca desde 500 m y se amplía '
        'solo si no hay terrenos aptos, independientemente del radio del mapa. '
        'Las demás casas no intervienen salvo que aceptes otra propuesta.'
    )
    if p.get('reference_ids'):
        result['messages'][-1]=f'Se usan {len(reference_ids)} casas de la propuesta aceptada. Se promedian únicamente sus precios ajustados a tus metrajes; las demás quedan como referencia.'
    result['messages'].extend(age_messages(p, selected_rows))
    result['selection_method']='age_proximity' if p.get('age') is not None else 'nearest_group'
    result.update(built_unit_min=built_unit_min, built_unit_max=built_unit_max,
                  built_unit_dispersion=(built_unit_max-built_unit_min)/(built_unit or 1))
    dispersion_ratio=built_unit_max/built_unit_min if built_unit_min > 0 else float('inf')
    if dispersion_ratio > 2.5:
        result['messages'].append(
            f'Los aportes observados están muy dispersos '
            f'({_unit_message(built_unit_min)} a {_unit_message(built_unit_max)}); '
            f'revisa los comparables seleccionados.'
        )
    land_value=p['land']*unit
    total=land_value+p['built']*built_unit
    # Spread of adjusted comparables, not a calibrated confidence interval.
    estimates=sorted(d['target_estimate'] for d in result['breakdown'] if d['usable'])
    result.update(status='ok',built_unit_method=built_unit_method,built_reference_id=built_reference_id,
        recommended_ids=reference_ids,
        new={'total':total,'land_value':land_value,'built_value':p['built']*built_unit,
        'built_unit':built_unit, 'range_low':estimates[0],
        'range_high':estimates[-1],
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
    target = p.get('property_type','Casa')
    overall = land if target == 'Terreno' or land_only(p) else built if target in ('Departamento','Oficina') else (land+built)/2
    return {'land_similarity':round(land,1),'built_similarity':round(built,1),
            'distance_similarity':round(distance,1),'overall_similarity':round(overall,1)}


def calculate_same_type(records,p,excluded=()):
    target=p['property_type'];is_land=target=='Terreno';area='land' if is_land else 'built'
    excluded=set(excluded)
    eligible=[r for r in records if r['kind']==target and not r['issues'] and r['id'] not in excluded and r['distance']<=p['radius']]
    count=len(eligible)
    limit=count if count<=3 else 3 if count<=15 else 4 if count<=30 else 5
    pool=selection_pool(eligible,p)
    if p.get('age') is not None and not is_land and pool:
        best_score=selection_metrics(pool[0],p)['selection_score']
        pool=[r for r in pool if best_score-selection_metrics(r,p)['selection_score']<=8]
    rows=pool[:min(limit,len(pool))]
    if rows:
        first=rows[0]
        close=[r for r in rows if r['distance']<=200 and abs(r['distance']-first['distance'])<=50 and
               surface_similarity(r.get(area),p.get(area))>=70]
        if len(close)>1:
            rows=close
    requested=p.get('reference_ids')
    if isinstance(requested,list) and 1<=len(requested)<=5 and len(set(requested))==len(requested) and all(i in {r['id'] for r in eligible} for i in requested):
        rows=[r for r in pool if r['id'] in requested]
        # A manually accepted fallback may include non-premieres.
        rows.extend(r for r in eligible if r['id'] in requested and r not in rows)
    units=sorted(r['price']/r[area] for r in rows)
    result={'version':VERSION,'model':'land' if is_land else 'built','property_type':target,
        'status':'insufficient','messages':[],'land_radius':p['radius'],'land_count':len(rows) if is_land else 0,
        'house_count':0 if is_land else len(rows),'land_ids':[r['id'] for r in rows] if is_land else [],
        'house_ids':[] if is_land else [r['id'] for r in rows], 'min_lands':MIN_LANDS,'min_houses':MIN_HOUSES,
        'new':None,'old':None,'land_unit':None,'breakdown':[],
        'eligible_count':count,'selection_count':len(rows),
        'selection_method':'age_proximity' if p.get('age') is not None and not is_land else 'nearest'}
    result['messages'].extend(age_messages(p, rows))
    if len(rows)>1 and all(r['distance']<=200 for r in rows):
        result['messages'].append(f'Se usan {len(rows)} comparables cercanos y aptos; los más lejanos quedan como referencia.')
    if rows:
        weights=[1/((r['distance'] or 1)+1) for r in rows]
        old_unit=sum(w*r['price']/r[area] for w,r in zip(weights,rows))/sum(weights)
        result['old']={'total':old_unit*p[area],'unit':old_unit,'houses':len(rows)}
    for r in rows:
        result['breakdown'].append({'id':r['id'],'method':result['model'],'offer_unit':r['price']/r[area],
            'area':r[area],'adjusted_total':r['price']/r[area]*p[area],'usable':True})
    minimum=1
    if len(rows)<minimum:
        result['messages'].append(f'Faltan comparables completos de {target.lower()}: {len(rows)} de {minimum} requeridos.')
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
