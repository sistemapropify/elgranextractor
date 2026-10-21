"""Separate original PDF layers and propose street-facing sides. No D1 writes."""
import argparse
import collections
import csv
import hashlib
import html
import io
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ezdxf
import fitz
import numpy as np
from PIL import Image, ImageDraw
from shapely import set_precision
from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.ops import polygonize_full, unary_union
from shapely.strtree import STRtree

CONFIG = {
    'manzanas': ('Manzanas · trazado original', ['MANZANA'], '#2563eb'),
    'lotes': ('Lotes · trazado original', ['Lotes'], '#116a5d'),
    'codigos_manzana': ('Códigos de manzana', ['CODIGO MZA'], '#7c3aed'),
    'numeros_manzana': ('Números / letras de manzana', ['Manzana txt'], '#a21caf'),
    'numeros_lote': ('Números de lote', ['LOTES_NUM'], '#111827'),
    'cotas_lados': ('Cotas · longitud de los lados', ['ACOTAMIENTO'], '#b42318'),
    'aranceles': ('Valores arancelarios', ['ARANCELES'], '#b45309'),
    'calles': ('Nombres de calles', ['CALLES'], '#536171'),
    'cuadras': ('Cuadras y par / impar', ['CUADRA'], '#64748b'),
}
MAX_X = 1600  # Main drawing only; inset maps begin to the right of this limit.
TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def flatten(item, matrix):
    kind = item[0]
    if kind == 'l':
        points = item[1:3]
    elif kind == 'qu':
        q = item[1]
        points = [q.ul,q.ur,q.lr,q.ll,q.ul]
    elif kind == 're':
        r = item[1]
        points = [r.tl,r.tr,r.br,r.bl,r.tl]
    elif kind == 'c':
        a,b,c,d = item[1:5]
        points = [fitz.Point(*[(1-t)**3*a[j]+3*(1-t)**2*t*b[j]+3*(1-t)*t*t*c[j]+t**3*d[j]
                              for j in (0,1)]) for t in np.linspace(0,1,33)]
    else:
        return []
    return [tuple(p*matrix) for p in points]


def svg_path(drawing, matrix):
    commands = []
    last = None
    def xy(p):
        p = p*matrix
        return f'{p.x:.4f},{p.y:.4f}'
    for item in drawing['items']:
        kind = item[0]
        if kind in ('l','c'):
            start = item[1]
            if last is None or abs(last-start)>.0001:
                commands.append('M'+xy(start))
            if kind=='l':
                commands.append('L'+xy(item[2]));last=item[2]
            else:
                commands.append('C'+' '.join(xy(p) for p in item[2:5]));last=item[4]
        else:
            pts=flatten(item,matrix)
            if pts:
                commands.append('M'+' L'.join(f'{x:.4f},{y:.4f}' for x,y in pts)+' Z')
            last=None
    return ' '.join(commands)


def path_element(drawing,matrix):
    width=max(float(drawing.get('width') or 0),.12)
    fill='currentColor' if drawing.get('fill') is not None else 'none'
    stroke='currentColor' if drawing.get('color') is not None else 'none'
    return f'<path d="{svg_path(drawing,matrix)}" fill="{fill}" stroke="{stroke}" stroke-width="{width:.4f}" stroke-linecap="round" stroke-linejoin="round"/>'


def group_labels(drawings, matrix, gap):
    bounds=[d['rect']*matrix for d in drawings]
    shapes=[box(r.x0-gap,r.y0-gap,r.x1+gap,r.y1+gap) for r in bounds]
    tree=STRtree(shapes);parents=list(range(len(shapes)))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for i,shape in enumerate(shapes):
        for j in tree.query(shape,predicate='intersects'):
            a,b=root(i),root(int(j))
            if a!=b:parents[b]=a
    groups=collections.defaultdict(list)
    for i,d in enumerate(drawings):groups[root(i)].append(d)
    return list(groups.values())


def ocr_group(group,matrix,kind):
    bounds=fitz.Rect(group[0]['rect']*matrix)
    for d in group[1:]:bounds|=d['rect']*matrix
    points=np.array([[(r.x0+r.x1)/2,(r.y0+r.y1)/2] for r in [d['rect']*matrix for d in group]])
    angle=0
    if len(points)>1:
        _,_,basis=np.linalg.svd(points-points.mean(axis=0),full_matrices=False)
        direction=basis[0]
        if direction[0]<0:direction=-direction
        angle=math.degrees(math.atan2(direction[1],direction[0]))
    # Main lot and block numbers are upright; dimensions follow their side.
    if kind not in ('cotas_lados','calles'):angle=0
    scale=13
    image=Image.new('L',(max(1,math.ceil(bounds.width*scale))+60,max(1,math.ceil(bounds.height*scale))+60),255)
    ink=ImageDraw.Draw(image)
    for d in group:
        for item in d['items']:
            pts=flatten(item,matrix)
            if pts:
                ink.line([((x-bounds.x0)*scale+30,(y-bounds.y0)*scale+30) for x,y in pts],
                         fill=0,width=max(1,round((d.get('width') or .15)*scale)))
    pattern=(r'\d{1,4}[.,]\d{2}' if kind=='cotas_lados' else r'\d{5}' if kind=='codigos_manzana'
             else r'[A-Z0-9 .\-\']+' if kind=='calles' else r'[0-9A-Z]+(?:[-–][0-9A-Z]+)?')
    whitelist=('0123456789.,' if kind=='cotas_lados' else '0123456789' if kind=='codigos_manzana'
               else "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ .'-" if kind=='calles' else '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-')
    attempts=[]
    rotations=(0,180) if kind in ('cotas_lados','calles') else (0,)
    for extra in rotations:
        sample=image.rotate(angle+extra,expand=True,fillcolor=255,resample=Image.Resampling.BICUBIC)
        stream=io.BytesIO();sample.save(stream,format='PNG')
        import os
        env=dict(os.environ,OMP_THREAD_LIMIT='1')
        for psm in ([8,7,13] if kind in ('codigos_manzana','numeros_manzana') else [8,7] if kind=='numeros_lote' else [7,8] if kind=='calles' else [7]):
          try:
            result=subprocess.run([TESSERACT,'stdin','stdout','-l','eng','--psm',str(psm),'-c','tessedit_char_whitelist='+whitelist,'tsv'],
                                  input=stream.getvalue(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=8,env=env)
            words=[r for r in csv.DictReader(io.StringIO(result.stdout.decode('utf-8',errors='replace')),delimiter='\t')
                   if r.get('text','').strip() and float(r.get('conf',-1))>=0]
            text=(' ' if kind=='calles' else '').join(r['text'].strip() for r in words)
            confidence=min((float(r['conf']) for r in words),default=0)
            if re.fullmatch(pattern,text):attempts.append((confidence,text,angle+extra))
            if confidence>=92 and re.fullmatch(pattern,text):break
          except (OSError,subprocess.TimeoutExpired,ValueError):pass
    score,text,used_angle=max(attempts,default=(0,None,angle))
    return {'texto_propuesto':text,'confianza_ocr':round(score,2),
            'estado_lectura':'propuesta_ocr_requiere_cotejo' if text else 'solo_vector_sin_lectura',
            'valor_numerico_propuesto':float(text.replace(',','.')) if text and kind=='cotas_lados' else None,
            'bbox_pdf':list(bounds),'posicion_pdf':[(bounds.x0+bounds.x1)/2,(bounds.y0+bounds.y1)/2],
            'angulo_ocr':round(used_angle,3),'trazados_originales':len(group)}


def source_block_faces(drawings,matrix):
    lines=[]
    for drawing in drawings:
        for item in drawing['items']:
            pts=flatten(item,matrix)
            if len(set(pts))>1:lines.append(set_precision(LineString(pts),.001))
    faces,cuts,dangles,invalid=polygonize_full(unary_union(lines))
    return [p for p in faces.geoms if p.area>=1 and p.is_valid],len(dangles.geoms)


def associate(records,sides,labels,layers,matrix):
    """Relate source labels and visible roads; ambiguous facts remain unknown."""
    polygons=[Polygon(r['geometry']['coordinates'][0],r['geometry']['coordinates'][1:]) for r in records]
    poly_tree=STRtree(polygons)
    by_id={r['id_tecnico']:r for r in records}
    for label in labels.get('numeros_lote',[]):
        if not label['texto_propuesto'] or label['confianza_ocr']<85:continue
        # Names such as JARDIN and malformed OCR fragments remain source labels;
        # they are not silently turned into parcel numbers or land-use facts.
        if not re.fullmatch(r'[0-9]{1,4}[A-Z]?(?:[-–][0-9]{1,4}[A-Z]?)?',label['texto_propuesto']):continue
        matches=poly_tree.query(Point(label['posicion_pdf']),predicate='within')
        label['lotes_candidatos']=[records[int(i)]['id_tecnico'] for i in matches]
        if len(matches)==1:records[int(matches[0])].setdefault('etiquetas_lote_propuestas',[]).append(label['texto_propuesto'])
    block_shapes,dangles=source_block_faces(layers['manzanas'],matrix)
    blocks=[]
    for i,shape in enumerate(block_shapes,1):
        codes=[l for l in labels.get('codigos_manzana',[]) if l['texto_propuesto'] and l['confianza_ocr']>=80 and shape.covers(Point(l['posicion_pdf']))]
        blocks.append({'id':'S32-M'+str(i).zfill(3),'codigo_manzana_propuesto':codes[0]['texto_propuesto'] if len(codes)==1 else None,
                       'codigo_refs':[c['id'] for c in codes],'estado':'contorno_original_cerrado_pendiente_cotejo','geometry':mapping(shape)})
    components=unary_union(polygons)
    physical=list(components.geoms) if hasattr(components,'geoms') else [components]
    street_labels=[]
    for label in labels.get('calles',[]):
        text=label.get('texto_propuesto') or ''
        # Distinct road names are needed for a corner proposal. Nearby glyphs alone
        # do not establish either a road or two different roads.
        normalized=' '.join(re.sub(r'[^A-Z0-9 ]',' ',text.upper()).split())
        if label['confianza_ocr']>=75 and re.match(r'^(AV|CA|CALLE|AVENIDA|PJ|PJE|PASAJE|JR|JIRON|PL)\s+\S',normalized):
            label['calle_identificada_propuesta']=normalized
            street_labels.append(label)
    street_points=[Point(l['posicion_pdf']) for l in street_labels]
    street_tree=STRtree(street_points) if street_points else None
    interior=components.buffer(-.15)
    edge_shapes=[LineString(s['geometry']['coordinates']) for s in sides]
    edge_tree=STRtree(edge_shapes)
    for label in labels.get('cotas_lados',[]):
        point=Point(label['posicion_pdf']);near=edge_tree.query(point.buffer(9),predicate='intersects')
        angle=label.get('angulo_ocr',0)%180
        candidates=[]
        for ix in near:
            ix=int(ix);edge=edge_shapes[ix];a,b=edge.coords[0],edge.coords[-1]
            direction=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
            if abs((direction-angle+90)%180-90)>18:continue
            candidates.append((edge.distance(point),ix))
        candidates.sort();label['lados_candidatos']=[sides[i]['id'] for distance,i in candidates[:4]]
        if label.get('texto_propuesto') and label['confianza_ocr']>=85 and candidates:
            for distance,i in candidates:
                if distance>candidates[0][0]+.2:break
                sides[i]['cota_refs'].append(label['id']);sides[i].setdefault('cotas_propuestas',[]).append(label['valor_numerico_propuesto'])
    grouped=collections.defaultdict(list)
    for side,edge in zip(sides,edge_shapes):
        grouped[side['lote_ref']].append((side,edge))
        side.update(tipo_lado='pendiente',estado='pendiente_orientacion',calle_refs=[],calles_propuestas=[])
        values=list(dict.fromkeys(side.get('cotas_propuestas',[])))
        side['longitud_lado_propuesta']=values[0] if len(values)==1 else None
        side['unidad_longitud']='segun_plano_sin_confirmacion_independiente'
    for record,polygon in zip(records,polygons):
        nums=list(dict.fromkeys(record.get('etiquetas_lote_propuestas',[])))
        record['numero_lote_propuesto']=nums[0] if len(nums)==1 else None
        overlaps=[(polygon.intersection(sh).area/polygon.area,b) for sh,b in zip(block_shapes,blocks)]
        matches=[b for ratio,b in overlaps if ratio>=.98]
        record['manzana_ref']=matches[0]['id'] if len(matches)==1 else None
        record['codigo_manzana_propuesto']=matches[0]['codigo_manzana_propuesto'] if len(matches)==1 else None
        component=next((g for g in physical if g.covers(polygon.representative_point())),None)
        traditional=[l for l in labels.get('numeros_manzana',[]) if l.get('texto_propuesto') and l['confianza_ocr']>=80 and component is not None and component.covers(Point(l['posicion_pdf']))]
        traditional_names=list(dict.fromkeys(l['texto_propuesto'] for l in traditional))
        record['numero_manzana_propuesto']=traditional_names[0] if len(traditional_names)==1 else None
        record['numero_manzana_refs']=[l['id'] for l in traditional]
        row=grouped[record['id_tecnico']];road_sides=[]
        for k,(side,edge) in enumerate(row):
            if k not in record['lados_expuestos'] or street_tree is None:continue
            midpoint=edge.interpolate(.5,normalized=True)
            a,b=edge.coords[0],edge.coords[-1];direction=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
            for ix in street_tree.query(midpoint.buffer(80),predicate='intersects'):
                label=street_labels[int(ix)];point=street_points[int(ix)]
                if abs((direction-label['angulo_ocr']+90)%180-90)>25:continue
                if edge.distance(point)>65:continue
                # A road annotation across another lot does not establish frontage.
                if LineString([midpoint,point]).intersection(interior).length>.5:continue
                side['calle_refs'].append(label['id']);side['calles_propuestas'].append(label['calle_identificada_propuesta'])
            if side['calle_refs']:road_sides.append(k)
        roads=set(name for k in road_sides for name in row[k][0]['calles_propuestas'])
        record.update(es_esquina=None,es_pasante=None,frente_parque=None,estado_orientacion='pendiente_confirmacion',
                      calles_propuestas=sorted(roads),criterio_frente='lado_expuesto_paralelo_a_nombre_de_via_con_trayecto_sin_cruzar_lotes',
                      criterio_esquina='dos_vias_identificadas_distintas_y_lados_contiguos_no_colineales',
                      estado_esquina='pendiente_evidencia_suficiente',lados_con_indicio_de_calle=road_sides)
        if len(roads)==1 and len(road_sides)==1 and len(row)==4 and polygon.simplify(.12).equals(polygon.simplify(.12).convex_hull):
            front=road_sides[0];row[front][0]['tipo_lado']='frente';row[(front+2)%4][0]['tipo_lado']='fondo'
            midpoint=row[front][1].interpolate(.5,normalized=True);forward=(polygon.centroid.x-midpoint.x,polygon.centroid.y-midpoint.y);left=(forward[1],-forward[0])
            for k in ((front+1)%4,(front-1)%4):
                q=row[k][1].interpolate(.5,normalized=True)
                row[k][0]['tipo_lado']='izquierda' if (q.x-polygon.centroid.x)*left[0]+(q.y-polygon.centroid.y)*left[1]>0 else 'derecha'
            record['estado_orientacion']='propuesta_geometrica_con_calle_identificada'
        else:
            for k in road_sides:row[k][0]['tipo_lado']='frente_multiple' if len(roads)>1 else 'frente'
        if len(roads)>=2:
            for ka in road_sides:
                for kb in road_sides:
                    if ka>=kb or set(row[ka][0]['calles_propuestas']) & set(row[kb][0]['calles_propuestas']):continue
                    ea,eb=row[ka][1],row[kb][1]
                    a,b=ea.coords;c,d=eb.coords
                    va=np.array(b)-a;vb=np.array(d)-c
                    angle=math.degrees(math.acos(min(1,abs(float(va@vb))/np.linalg.norm(va)/np.linalg.norm(vb))))
                    if ea.distance(eb)<.25 and angle>=20:
                        record.update(es_esquina=True,estado_esquina='propuesta_dos_calles_requiere_cotejo')
                    elif angle<20 and abs(ka-kb)>1 and abs(ka-kb)!=len(row)-1:
                        record['es_pasante']=True
        for side,edge in row:
            if side['tipo_lado']!='pendiente':side['estado']='propuesta_requiere_cotejo'
    return blocks,{'manzanas_cerradas':len(blocks),'aristas_manzana_sin_cierre':dangles,
                   'calles_con_nombre_propuesto':len(street_labels)}


def recover(layers,matrix):
    segments=[]
    for drawing in layers['lotes']:
        for item in drawing['items']:
            pts=flatten(item,matrix)
            if len(set(pts))>1:segments.append(set_precision(LineString(pts),.001))
    faces,cuts,dangles,invalid=polygonize_full(unary_union(segments))
    # Raw linework is always retained. Tiny polygonization slivers are not lots.
    polygons=[p for p in faces.geoms if p.area>=1 and p.is_valid]
    merged=unary_union(polygons)
    blocks=list(merged.geoms) if hasattr(merged,'geoms') else [merged]
    block_tree=STRtree(blocks)
    records,sides=[],[]
    for index,polygon in enumerate(sorted(polygons,key=lambda p:(round(p.centroid.y,1),round(p.centroid.x,1))),1):
        rid=f'S32-F{index:04}'
        block=blocks[int(block_tree.nearest(polygon.representative_point()))]
        simplified=polygon.simplify(.12,preserve_topology=True)
        coords=list(simplified.exterior.coords)
        edges=[LineString([a,b]) for a,b in zip(coords,coords[1:]) if a!=b]
        exposed=[]
        for k,edge in enumerate(edges):
            ratio=edge.intersection(block.boundary.buffer(.08)).length/edge.length
            if ratio>.85:exposed.append(k)
        corner=through=None;roles={}
        record={'id_tecnico':rid,'numero_lote_propuesto':None,'codigo_manzana_propuesto':None,
                'es_esquina':corner,'es_pasante':through,'frente_parque':None,
                'estado_geometria':'cara_cerrada_recuperada_no_validada_como_lote',
                'estado_orientacion':'propuesta_geometrica' if roles else 'pendiente_confirmacion',
                'criterio_frente':'borde_expuesto_con_nombre_de_calle_cercano',
                'criterio_izquierda_derecha':'observador_en_la_calle_mirando_hacia_el_lote',
                'estado_parque':'pendiente_capa_de_parques_confirmada',
                'area_pdf_pt2':round(polygon.area,4),'geometry':mapping(polygon),
                'numero_lados':len(edges),'lados_expuestos':exposed,'lados_con_indicio_de_calle':[]}
        records.append(record)
        for k,edge in enumerate(edges):
            sides.append({'id':rid+f'-L{k+1:02}','lote_ref':rid,'tipo_lado':roles.get(k,'pendiente'),
                          'longitud_lado_propuesta':None,'cota_refs':[],
                          'longitud_grafica_pdf_pt':round(edge.length,4),'geometry':mapping(edge),
                          'estado':'propuesta_requiere_cotejo' if k in roles else 'pendiente_orientacion'})
    return records,sides,{'caras_cerradas':len(polygons),'agrupaciones_contiguas':len(blocks),
                         'aristas_colgantes':len(dangles.geoms),'anillos_invalidos':len(invalid.geoms),
                         'caras_menores_de_1_pt2_excluidas':sum(p.area<1 for p in faces.geoms)}


def export_tables(output,payload):
    """Separate one-row-per-face, one-row-per-side and source annotation tables."""
    side_map=collections.defaultdict(list)
    for side in payload['sides']:side_map[side['lote_ref']].append(side)
    fields=['id_tecnico','codigo_manzana_propuesto','numero_manzana_propuesto','numero_lote_propuesto',
            'es_esquina','es_pasante','frente_parque','estado_geometria','estado_esquina','estado_orientacion',
            'calles_propuestas','frente_cotas_propuestas','frente_multiple_cotas_propuestas','fondo_cotas_propuestas',
            'izquierda_cotas_propuestas','derecha_cotas_propuestas','pendiente_cotas_propuestas']
    with (output/'lotes.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for record in payload['lots']:
            row={key:record.get(key) for key in fields}
            row['calles_propuestas']=json.dumps(row['calles_propuestas'],ensure_ascii=False)
            for role in ('frente','frente_multiple','fondo','izquierda','derecha','pendiente'):
                row[role+'_cotas_propuestas']=json.dumps([s['longitud_lado_propuesta'] for s in side_map[record['id_tecnico']]
                    if s['tipo_lado']==role and s['longitud_lado_propuesta'] is not None])
            writer.writerow(row)
    for filename,rows in [('lados.csv',payload['sides']),('manzanas.csv',payload['blocks'])]:
        keys=sorted(set().union(*(r.keys() for r in rows))-{'geometry'})
        with (output/filename).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader()
            for row in rows:writer.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in keys})
    annotations=[]
    for kind,rows in payload['labels'].items():
        for row in rows:annotations.append({'capa':kind,**row})
    keys=['id','capa','texto_propuesto','confianza_ocr','estado_lectura','valor_numerico_propuesto','posicion_pdf','lados_candidatos','lotes_candidatos']
    with (output/'anotaciones.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader()
        for row in annotations:writer.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row.get(k),list) else row.get(k) for k in keys})
    width,height=payload['source']['viewbox'][2:]
    header=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
    def polygon_path(geometry):
        return ' '.join('M'+' L'.join(f'{x:.4f},{y:.4f}' for x,y in ring)+' Z' for ring in geometry['coordinates'])
    for role,color in [('frente','#079455'),('frente_multiple','#ca8a04'),('fondo','#ef4444'),('izquierda','#2563eb'),('derecha','#a855f7'),('pendiente','#9ca3af')]:
        content=''.join('<path d="M'+' L'.join(f'{x:.4f},{y:.4f}' for x,y in s['geometry']['coordinates'])+'"/>' for s in payload['sides'] if s['tipo_lado']==role)
        (output/('lados_'+role+'.svg')).write_text(header+f'<g fill="none" stroke="{color}" stroke-width="1">'+content+'</g></svg>',encoding='utf8')
    corners=''.join(f'<path d="{polygon_path(r["geometry"])}"><title>{r["id_tecnico"]} · esquina propuesta</title></path>' for r in payload['lots'] if r['es_esquina'] is True)
    (output/'esquinas_propuestas.svg').write_text(header+'<g fill="#f59e0b55" fill-rule="evenodd" stroke="#d97706">'+corners+'</g></svg>',encoding='utf8')


def main(source,output,do_ocr=True,reuse_labels=None,refresh_labels=()):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    original=Path(source).read_bytes();doc=fitz.open(stream=original,filetype='pdf');page=doc[0]
    matrix=page.rotation_matrix;drawings=page.get_drawings();height=page.rect.height
    groups={key:[d for d in drawings if d.get('layer') in origins and (d['rect']*matrix).x0<MAX_X]
            for key,(_,origins,_) in CONFIG.items()}
    width=MAX_X;elements={key:'\n'.join(path_element(d,matrix) for d in group) for key,group in groups.items()}
    svg_header=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
    for key,markup in elements.items():
        color=CONFIG[key][2]
        (output/(key+'.svg')).write_text(svg_header+f'<g color="{color}">'+markup+'</g></svg>',encoding='utf-8')
    records,sides,qa=recover(groups,matrix)
    labels={}
    if reuse_labels:
        previous=json.loads(Path(reuse_labels).read_text(encoding='utf8'))
        if previous['source']['sha256']!=hashlib.sha256(original).hexdigest():raise ValueError('Las etiquetas previas no corresponden al mismo PDF.')
        for key,rows in previous['labels'].items():
            if key in refresh_labels or not any(r.get('texto_propuesto') for r in rows):continue
            labels[key]=rows
            for label in rows:label['lectura_reutilizada_mismo_original']=True
    if do_ocr:
        tasks=[]
        for key,gap in [('codigos_manzana',6),('numeros_manzana',4),('calles',2.5),('numeros_lote',1.5),('cotas_lados',1.1)]:
            if key in labels:continue
            drawings=groups[key]
            if key=='numeros_manzana':
                # Keep the surrounding circle in SVG/DXF, but omit it from OCR.
                drawings=[d for d in drawings if not (len(d['items'])==4 and all(i[0]=='c' for i in d['items']) and (d['rect']*matrix).height>16)]
            tasks.extend((key,g) for g in group_labels(drawings,matrix,gap))
        def work(task):
            key,g=task
            return key,ocr_group(g,matrix,key)
        print(json.dumps({'ocr_groups':len(tasks)}),flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for n,(key,result) in enumerate(pool.map(work,tasks),1):
                result['id']=key+f'-{len(labels.get(key,[]))+1:04}'
                labels.setdefault(key,[]).append(result)
                if n%100==0:print(json.dumps({'ocr_completed':n,'total':len(tasks)}),flush=True)
    blocks,block_qa=associate(records,sides,labels,groups,matrix);qa.update(block_qa)
    payload={'source':{'file':Path(source).name,'sha256':hashlib.sha256(original).hexdigest(),
                       'page':1,'date_printed':'ENERO 2017','crs':'LOCAL_PDF_DISPLAY_POINTS',
                       'georeferenced':False,'unit':'PDF point','y_axis':'down',
                       'viewbox':[0,0,width,height],
                       'original_layers':{str(k):v['name'] for k,v in doc.get_ocgs().items()}},
             'layers':{key:{'name':title,'source_layers':origins,'vector_paths':len(groups[key])}
                       for key,(title,origins,color) in CONFIG.items()},
             'extraction_format':'sector32-vectores-v2','qa':qa,'lots':records,'blocks':blocks,'sides':sides,'labels':labels,
             'notes':['Las capas SVG conservan los trazos originales y sus curvas cúbicas.',
                      'Las caras, orientación, esquina y lecturas OCR son propuestas revisables.',
                      'Código de manzana y rótulo tradicional de manzana se conservan separados tal como figuran en sus capas.',
                      'Esquina requiere indicios de dos calles identificadas distintas; los demás casos quedan desconocidos.',
                      'Las unidades de dibujo son puntos PDF, no metros ni coordenadas geográficas.',
                      'Las cotas son longitudes de lados, no áreas ni perímetros totales.',
                      'frente_parque queda nulo sin una capa confirmada de parques.']}
    (output/'sector32.capas.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    with (output/'lotes_y_lados.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['lote_tecnico','numero_lote_propuesto','lado','tipo_lado_propuesto','longitud_lado_propuesta','es_esquina_propuesto','es_pasante_propuesto','frente_parque','estado'])
        by_id={r['id_tecnico']:r for r in records}
        for side in sides:
            r=by_id[side['lote_ref']]
            writer.writerow([r['id_tecnico'],r['numero_lote_propuesto'],side['id'],side['tipo_lado'],side['longitud_lado_propuesta'],r['es_esquina'],r['es_pasante'],r['frente_parque'],side['estado']])
    cad=ezdxf.new('R2010');cad.header['$INSUNITS']=0;msp=cad.modelspace()
    for index,(key,group) in enumerate(groups.items(),1):
        cad.layers.new(key,dxfattribs={'color':(index%7)+1})
        for drawing in group:
            for item in drawing['items']:
                pts=flatten(item,matrix)
                if len(set(pts))>1:msp.add_lwpolyline([(x,height-y) for x,y in pts],dxfattribs={'layer':key})
    for role,color in [('frente',3),('frente_multiple',2),('fondo',1),('izquierda',5),('derecha',6),('pendiente',8)]:
        name='lados_'+role;cad.layers.new(name,dxfattribs={'color':color})
        for side in sides:
            if side['tipo_lado']==role:msp.add_lwpolyline([(x,height-y) for x,y in side['geometry']['coordinates']],dxfattribs={'layer':name})
    cad.appids.new('PROMETEO')
    for name,color,items in [('poligonos_lotes_pendientes',4,records),('esquinas_propuestas',2,[r for r in records if r['es_esquina'] is True]),('manzanas_cerradas_pendientes',5,blocks)]:
        cad.layers.new(name,dxfattribs={'color':color})
        for row in items:
            for ring in row['geometry']['coordinates']:
                entity=msp.add_lwpolyline([(x,height-y) for x,y in ring],close=True,dxfattribs={'layer':name})
                entity.set_xdata('PROMETEO',[(1000,json.dumps({k:row[k] for k in ('id','id_tecnico','codigo_manzana_propuesto','numero_manzana_propuesto','numero_lote_propuesto') if k in row},ensure_ascii=True))])
    for kind,rows in labels.items():
        name='lectura_'+kind;cad.layers.new(name,dxfattribs={'color':8})
        for row in rows:
            if not row['texto_propuesto']:continue
            x,y=row['posicion_pdf'];entity=msp.add_text(row['texto_propuesto'],dxfattribs={'layer':name,'height':max(1,(row['bbox_pdf'][3]-row['bbox_pdf'][1])*.7),'rotation':-row['angulo_ocr'],'insert':(x,height-y)})
            entity.set_xdata('PROMETEO',[(1000,row['id']),(1040,row['confianza_ocr'])])
    cad.saveas(output/'sector32_capas.dxf')
    export_tables(output,payload)
    make_viewer(output,svg_header,elements,records,sides,payload)
    print(json.dumps({'output':str(output),'qa':qa,'side_roles':dict(collections.Counter(s['tipo_lado'] for s in sides)),
                      'corner_proposals':dict(collections.Counter(str(r['es_esquina']) for r in records)),
                      'ocr':{k:sum(bool(x['texto_propuesto']) for x in v) for k,v in labels.items()}},ensure_ascii=False),flush=True)


def make_viewer(output,svg_header,elements,records,sides,payload):
    controls=''.join(f'<label><input type="checkbox" data-layer="{key}" '+('checked' if key not in ('aranceles','cuadras') else '')+f'><span style="color:{color}">●</span> {html.escape(title)}</label>' for key,(title,_,color) in CONFIG.items())
    layers=''.join(f'<g id="{key}" color="{CONFIG[key][2]}"'+(' style="display:none"' if key in ('aranceles','cuadras') else '')+f'>{markup}</g>' for key,markup in elements.items())
    def polygon_path(geometry):
        return ' '.join('M'+' L'.join(f'{x:.3f},{y:.3f}' for x,y in ring)+' Z' for ring in geometry['coordinates'])
    areas=''.join(f'<path data-record="{r["id_tecnico"]}" d="{polygon_path(r["geometry"])}"/>' for r in records)
    corners=''.join(f'<path d="{polygon_path(r["geometry"])}"/>' for r in records if r['es_esquina'] is True)
    colors={'frente':'#079455','frente_multiple':'#ca8a04','fondo':'#ef4444','izquierda':'#2563eb','derecha':'#a855f7','pendiente':'#9ca3af'}
    marks=''.join(f'<path stroke="{colors[s["tipo_lado"]]}" d="M'+' L'.join(f'{x:.3f},{y:.3f}' for x,y in s['geometry']['coordinates'])+'"/>' for s in sides if s['tipo_lado']!='pendiente')
    compact=json.dumps({'lots':{r['id_tecnico']:{k:v for k,v in r.items() if k!='geometry'} for r in records},'sides':sides,
        'dimensions':payload['labels'].get('cotas_lados',[]),'summary':{'numbered':sum(r['numero_lote_propuesto'] is not None for r in records),
        'corners':sum(r['es_esquina'] is True for r in records),'lengths':sum(s['longitud_lado_propuesta'] is not None for s in sides)}},ensure_ascii=False).replace('<','\\u003c')
    template=Path(__file__).with_name('pdf_vectors_viewer.html').read_text(encoding='utf8')
    result=template.replace('__CONTROLS__',controls).replace('__SVG__',svg_header+layers).replace('__CORNERS__',corners).replace('__AREAS__',areas).replace('__SIDES__',marks).replace('__DATA__',compact)
    (output/'visor-sector32.html').write_text(result,encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');parser.add_argument('--output',required=True);parser.add_argument('--no-ocr',action='store_true');parser.add_argument('--reuse-labels');parser.add_argument('--refresh-label',action='append',default=[])
    args=parser.parse_args();main(args.source,args.output,not args.no_ocr,args.reuse_labels,args.refresh_label)
