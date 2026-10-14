"""Named fields in COFOPRI's report layout, including black text values.

Reports do not use the numbered gray cells of individual cadastral forms.
Headers are matched to their actual column cells; inline and boundary fields
have explicit layout rules rather than a nearest text guess.
"""
import re

HEADERS = {
    'FECHA': 'Fecha del reporte', 'HORA': 'Hora del reporte',
    'CUC-LOTE': 'CUC del lote', 'CUC-UNIDAD CATASTRAL': 'CUC de la unidad catastral',
    'DEPARTAMENTO': 'Departamento', 'PROVINCIA': 'Provincia', 'DISTRITO': 'Distrito',
    'SECT': 'Sector', 'MZA': 'Manzana catastral', 'LOTE': 'Lote',
    'NOMBRES Y APELLIDOS O RAZON SOCIAL': 'Nombres y apellidos o razón social',
    'TIPO DOCUMENTO': 'Tipo de documento', 'NRO DOCUMENTO': 'Número de documento',
    '(%)': 'Porcentaje de titularidad', 'CONDICION DEL TITULAR': 'Condición del titular',
    'TIPO VIA': 'Tipo de vía', 'NOMBRE VIA': 'Nombre de vía', 'NRO MUNICIPAL': 'Número municipal',
    'MANZANA': 'Manzana de la dirección', 'URBANIZACION-HU': 'Urbanización / habilitación urbana',
    'AREA LOTE (M2)': 'Área del lote (m²)', 'AREA CONSTRUIDA (M2)': 'Área construida (m²)',
    'USO': 'Uso del predio',
}
SIDES = {'FRENTE': 'Frente', 'DERECHA': 'Derecha', 'IZQUIERDA': 'Izquierda', 'FONDO': 'Fondo'}
OTHER_LABELS = {'DIRECCION DEL PREDIO', 'COLINDANCIAS DEL PREDIO', 'MEDIDAS PERIMETRICAS DEL PREDIO(M)'}


def norm(text):
    return ' '.join(text.upper().split())


def section(label, y, anchors):
    if label in ('FECHA', 'HORA', 'CUC-LOTE', 'CUC-UNIDAD CATASTRAL'):
        return 'Identificación del reporte'
    if label in ('DEPARTAMENTO','PROVINCIA','DISTRITO','SECT','MZA'):
        return 'Ubicación geográfica'
    if label in ('NOMBRES Y APELLIDOS O RAZON SOCIAL','TIPO DOCUMENTO','NRO DOCUMENTO','(%)','CONDICION DEL TITULAR'):
        return 'Titulares catastrales'
    if label == 'LOTE' and y < next((a['bbox'][1] for a in anchors if a['original_label']=='TIPO VIA'), 1e9):
        return 'Ubicación geográfica'
    return 'Datos del predio'


def extract_report(cells):
    anchors = []
    for c in cells:
        label = norm(c['text'])
        if label in HEADERS:
            anchors.append({'label':HEADERS[label], 'original_label':label, 'bbox':c['bbox'], 'cell_id':c['id'], 'values':[]})
    if not {'DEPARTAMENTO','PROVINCIA','DISTRITO','AREA LOTE (M2)'} <= {a['original_label'] for a in anchors}:
        return None
    for a in anchors:
        a['section'] = section(a['original_label'], a['bbox'][1], anchors)
    unmatched = []
    for c in cells:
        text, box = c['text'].strip(), c['bbox']
        if not text or norm(text) in set(HEADERS) | set(SIDES) | OTHER_LABELS:
            continue
        x, y = (box[0]+box[2])/2, (box[1]+box[3])/2
        inline = [a for a in anchors if a['original_label'] in ('FECHA','HORA','CONDICION DEL TITULAR')
                  and abs(a['bbox'][1]-box[1]) < 1 and abs(a['bbox'][2]-box[0]) < 1]
        if inline:
            a = inline[0]
        else:
            candidates = [a for a in anchors if a['original_label'] not in ('FECHA','HORA','CONDICION DEL TITULAR')
                          and a['bbox'][0]-.5 <= x <= a['bbox'][2]+.5 and a['bbox'][3] <= box[1]+1]
            # Boundary rows below the two boundary-column headers are handled
            # separately, never attributed to area or usage fields above them.
            boundary_top = min((s['bbox'][1] for s in cells if norm(s['text']) in SIDES), default=1e9)
            if y >= boundary_top:
                continue
            a = max(candidates,key=lambda a:a['bbox'][3]) if candidates else None
        if a:
            a['values'].append({'text':text,'bbox':box,'cell_id':c['id'],'row':round(y,1)})
        else:
            unmatched.append({'text':text,'bbox':box,'cell_id':c['id']})
    for side_cell in [c for c in cells if norm(c['text']) in SIDES]:
        b = side_cell['bbox']
        row = sorted([c for c in cells if c['bbox'][0] >= b[2]-1 and abs(c['bbox'][1]-b[1]) < 1
                      and abs(c['bbox'][3]-b[3]) < 1],key=lambda c:c['bbox'][0])
        for index, c in enumerate(row[:2]):
            side = SIDES[norm(side_cell['text'])]
            anchors.append({'label':('Colindancia · ' if index==0 else 'Medida perimétrica · ')+side+(' (m)' if index==1 else ''),
                            'original_label':side_cell['text'], 'section':'Linderos y medidas perimétricas',
                            'bbox':c['bbox'],'cell_id':c['id'],
                            'values':[{'text':c['text'],'bbox':c['bbox'],'cell_id':c['id'],'row':round((b[1]+b[3])/2,1)}] if c['text'] else []})
    for a in anchors:
        a['value'] = ' | '.join(v['text'] for v in a['values']) if a['values'] else None
        a['value_status'] = 'extracted' if a['values'] else 'blank'
    return {'named_fields':anchors,'unmapped_cells':unmatched,'extraction_status':'cadastral_report',
            'field_mapping_status':'mapped_report_headers'}
