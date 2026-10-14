"""Extract numbered COFOPRI fields, retaining cells and text for audit.

COFOPRI's generated forms identify entered values in blue and field numbers
in gray cells. Unknown layouts are retained and explicitly need review.
"""
import re


def extract_page(page):
    def blue(span):
        color = span.get('color', 0)
        red, green, value = (color >> 16) & 255, (color >> 8) & 255, color & 255
        return value > red + 60 and value > green + 60
    spans = [s for b in page.get_text('dict')['blocks'] if 'lines' in b
             for line in b['lines'] for s in line['spans'] if s['text'].strip()]
    characters = [{'text': c['c'], 'bbox': c['bbox'], 'size': s['size']} for b in page.get_text('rawdict')['blocks']
                  if 'lines' in b for line in b['lines'] for s in line['spans'] for c in s['chars']]
    rectangles = {}
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0] == 're':
                bbox = tuple(round(float(n), 2) for n in item[1])
                rectangles[bbox] = drawing.get('fill')

    def center(s):
        x0, y0, x1, y1 = s['bbox']
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    def inside(bbox, point):
        return bbox[0] - .4 <= point[0] <= bbox[2] + .4 and bbox[1] - .4 <= point[1] <= bbox[3] + .4

    def area(bbox):
        return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

    cells = []
    for bbox, fill in rectangles.items():
        contents = [s for s in spans if inside(bbox, center(s))]
        chars = sorted([c for c in characters if inside(bbox, center(c))], key=lambda c: (round(center(c)[1] / 3), c['bbox'][0]))
        text, previous = '', None
        for char in chars:
            if previous and abs(center(char)[1] - center(previous)[1]) > 3:
                text += ' '
            elif previous and char['bbox'][0] - previous['bbox'][2] > char['size'] * .35:
                text += ' '
            text += char['text']
            previous = char
        cells.append({'id': len(cells), 'bbox': list(bbox),
                      'text': ' '.join(text.split()),
                      'values': [s['text'].strip() for s in contents if blue(s)], 'fill': fill})
    sections = sorted([s for s in spans if s['size'] >= 7.9 and not blue(s)], key=lambda s: s['bbox'][1])
    fields = []
    for number_cell in cells:
        text, box, fill = number_cell['text'], number_cell['bbox'], number_cell['fill']
        match = re.search(r'(?<!\d)(\d{2,3})(?!\d)', text)
        if (not match or not 1 <= int(match[1]) <= 134 or not fill
                or max(fill) - min(fill) >= .02 or not .5 <= fill[0] <= .9 or box[2] - box[0] > 110):
            continue
        number = match[1]
        right = [c for c in cells if abs(c['bbox'][0] - box[2]) < 1 and
                 abs(c['bbox'][1] - box[1]) < 1 and abs(c['bbox'][3] - box[3]) < 1 and c['text'] and not re.fullmatch(r'\d{2,3}', c['text'])]
        label_cell = min(right, key=lambda c: area(c['bbox'])) if right else None
        if not label_cell and box[2] - box[0] > 16:
            below = [c for c in cells if abs(c['bbox'][0] - box[0]) < 1 and abs(c['bbox'][2] - box[2]) < 1
                     and abs(c['bbox'][1] - box[3]) < 1 and c['text'] and not c['values']]
            label_cell = min(below, key=lambda c: area(c['bbox'])) if below else None
        preceding = [s for s in sections if s['bbox'][1] < box[1] - 2]
        label = label_cell['text'] if label_cell else text[len(number):].strip()
        label = re.sub('^' + number + r'\s*', '', label)
        original_label = label
        if number == '11':
            label = 'NUMERO MUNICIPAL'
        elif number == '12':
            label = 'CONDICION DE NUMERACION'
        fields.append({'number': number, 'label': label,
                       'original_label': original_label,
                       'section': preceding[-1]['text'].strip() if preceding else 'Identificación catastral',
                       'bbox': [box[0], box[1], label_cell['bbox'][2] if label_cell else box[2], max(box[3], label_cell['bbox'][3]) if label_cell else box[3]],
                       'values': [], 'cell_id': number_cell['id']})
    unassigned = []
    for span in [s for s in spans if blue(s)]:
        x, y = center(span)
        # Values may sit to the right of a numbered heading or underneath it.
        same_row = [f for f in fields if f['bbox'][1] - 1 <= y <= f['bbox'][3] + 1 and x >= f['bbox'][0]]
        field = max(same_row, key=lambda f: f['bbox'][0]) if same_row else None
        if not field:
            candidates = [f for f in fields if f['bbox'][0] - 1 <= x <= f['bbox'][2] + 1 and f['bbox'][3] <= y + 1
                          and not any(f['bbox'][3] < s['bbox'][1] < y - 2 for s in sections)]
            field = max(candidates, key=lambda f: f['bbox'][3]) if candidates else None
        containing = [c for c in cells if inside(c['bbox'], (x, y))]
        cell = min(containing, key=lambda c: area(c['bbox'])) if containing else None
        value = {'text': span['text'].strip(), 'bbox': [round(n, 2) for n in span['bbox']],
                 'cell_id': cell['id'] if cell else None, 'row': round(y, 1)}
        if field:
            field['values'].append(value)
        else:
            unassigned.append(value)
    for field in fields:
        field['value'] = ' | '.join(v['text'] for v in field['values']) if field['values'] else None
        field['value_status'] = 'extracted' if field['values'] else 'blank'
    additional = []
    for cell in cells:
        # Unnumbered fields and the declarant/technician signature information.
        if ':' in cell['text'] and not cell['values'] and cell['bbox'][1] > page.rect.height * .75:
            label, value = cell['text'].split(':', 1)
            additional.append({'label': label.strip(), 'value': value.strip() or None, 'cell_id': cell['id'], 'bbox': cell['bbox']})
    for value in unassigned:
        cell = next((c for c in cells if c['id'] == value['cell_id']), None)
        left = [c for c in cells if cell and c['bbox'][2] <= cell['bbox'][0] + 1 and abs(c['bbox'][1] - cell['bbox'][1]) < 1 and c['text'] and not c['values']]
        if left:
            label = max(left, key=lambda c:c['bbox'][2])['text']
            additional.append({'label': label, 'value': value['text'], **value})
    result = {'numbered_fields': fields, 'cells': cells, 'unassigned_values': unassigned,
            'additional_fields': additional,
            'text_spans': [{k: s[k] for k in ('text', 'bbox', 'font', 'size', 'color')} for s in spans],
            'extraction_status': 'numbered_form' if fields else 'needs_review',
            'field_mapping_status': 'requires_validation'}
    if not fields and any('REPORTE CATASTRAL' in s['text'] for s in spans):
        from .report_fields import extract_report
        report = extract_report(cells)
        if report:
            result.update(report)
            result['additional_fields'] = []
            result['unassigned_values'] = report['unmapped_cells']
    return result
