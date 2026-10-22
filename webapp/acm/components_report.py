"""Editable client report using the same content and selection as the PDF."""
from io import BytesIO


def _fit_one_page(doc):
    """Fit the editable body to the available A4 height without dropping text."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.ns import qn
    from docx.shared import Pt
    from reportlab.pdfbase.pdfmetrics import stringWidth

    section = doc.sections[0]
    width = (section.page_width-section.left_margin-section.right_margin)/12700
    budget = (section.page_height-section.top_margin-section.bottom_margin)/12700-40

    def points(value):
        return value.pt if value is not None else 0

    def paragraph_height(p, available):
        style = p.style
        size = max([points(run.font.size) for run in p.runs]+[points(style.font.size) or points(doc.styles['Normal'].font.size)])
        before = points(p.paragraph_format.space_before if p.paragraph_format.space_before is not None else style.paragraph_format.space_before)
        after = points(p.paragraph_format.space_after if p.paragraph_format.space_after is not None else style.paragraph_format.space_after)
        available = max(10,available-points(p.paragraph_format.right_indent)-points(p.paragraph_format.left_indent))
        lines = 0
        for line in p.text.split('\n'):
            used = 0; lines += 1
            for word in line.split():
                length = stringWidth(word+' ','Helvetica',size)
                if used and used+length > available:
                    lines += 1; used = 0
                lines += int(length//available)
                used += length % available
        images = [int(node.get('cy'))/12700 for node in p._p.iter(qn('wp:extent'))]
        return before+after+max(lines*size*1.2,max(images,default=0)+size*.25)

    def height(parent, available):
        node = parent._tc if hasattr(parent,'_tc') else parent._element.body
        total = 0
        for child in node:
            if child.tag == qn('w:p'):
                total += paragraph_height(Paragraph(child,parent),available)
            elif child.tag == qn('w:tbl'):
                table = Table(child,parent)
                total += sum(max(height(cell,cell.width/12700) for cell in row.cells)+2 for row in table.rows)
        return total

    def paragraphs(parent):
        yield from parent.paragraphs
        for table in parent.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from paragraphs(cell)

    for _ in range(5):
        estimate = height(doc,width)
        if estimate <= budget:
            break
        factor = min(.95,budget/estimate*.97)
        for style in doc.styles:
            if style.type != 1: continue
            if style.font.size is not None: style.font.size=Pt(style.font.size.pt*factor)
            for name in ('space_before','space_after'):
                value=getattr(style.paragraph_format,name)
                if value is not None:setattr(style.paragraph_format,name,Pt(value.pt*factor))
        for p in paragraphs(doc):
            for run in p.runs:
                if run.font.size is not None:run.font.size=Pt(run.font.size.pt*factor)
            for name in ('space_before','space_after'):
                value=getattr(p.paragraph_format,name)
                if value is not None:setattr(p.paragraph_format,name,Pt(value.pt*factor))
            p.paragraph_format.widow_control=False
        for picture in doc.inline_shapes:
            picture.width=int(picture.width*factor);picture.height=int(picture.height*factor)


def build_acm_docx(params, records, result, excluded=(), generated_at=None, user=None, fetch_images=True):
    from .client_report import prepare_report, age, RESULT_LABELS
    from .components_pdf import _money, _number, _unit_price, _fecha_larga, _clean
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor
    data=prepare_report(params,records,result,excluded,generated_at,user,fetch_images)
    doc=Document();section=doc.sections[0]
    section.page_width=Inches(8.27);section.page_height=Inches(11.69)
    section.top_margin=Inches(.40);section.bottom_margin=Inches(.48)
    section.left_margin=Inches(.53);section.right_margin=Inches(.53)
    width=7.21
    for name in ('Normal','Title','Heading 1','Heading 2'):
        style=doc.styles[name];style.font.name='Arial';style.font.color.rgb=RGBColor.from_string('243238')
        style.paragraph_format.space_after=Pt(3)
    for node in doc.styles.element.iter(qn('w:pBdr')):
        node.getparent().remove(node)
    doc.styles['Normal'].font.size=Pt(8.5)
    doc.styles['Normal'].paragraph_format.line_spacing=1
    doc.styles['Title'].font.size=Pt(22);doc.styles['Title'].font.bold=True
    doc.styles['Title'].font.color.rgb=RGBColor.from_string('008F91')
    doc.styles['Heading 1'].font.size=Pt(13);doc.styles['Heading 1'].font.color.rgb=RGBColor.from_string('008F91')
    doc.styles['Heading 1'].paragraph_format.space_before=Pt(8)
    doc.styles['Heading 1'].paragraph_format.space_after=Pt(5)
    doc.core_properties.title='Análisis comparativo de mercado';doc.core_properties.author=data['author']
    def table(parent,widths):
        if parent is doc:t=parent.add_table(rows=1,cols=len(widths))
        else:t=parent.add_table(rows=1,cols=len(widths))
        t.autofit=False
        for c,w in zip(t.columns,widths):c.width=Inches(w)
        for c,w in zip(t.rows[0].cells,widths):
            c.width=Inches(w)
            pr=c._tc.get_or_add_tcPr();m=OxmlElement('w:tcMar')
            for side in ('top','left','bottom','right'):
                node=OxmlElement('w:'+side);node.set(qn('w:w'),'0');node.set(qn('w:type'),'dxa');m.append(node)
            pr.append(m)
        rowpr=t.rows[0]._tr.get_or_add_trPr();rowpr.append(OxmlElement('w:cantSplit'))
        return t
    def text(parent,value='',bold=False,size=None,color=None,first=False):
        p=parent.paragraphs[0] if first and parent.paragraphs else parent.add_paragraph()
        p.paragraph_format.space_after=Pt(2)
        r=p.add_run(str(value));r.bold=bold
        if size:r.font.size=Pt(size)
        if color:r.font.color.rgb=RGBColor.from_string(color)
        return p
    def label(parent,value,first=False):return text(parent,value,size=7,color='66757A',first=first)
    def image(parent,content,w,h,placeholder='Sin fotografía disponible',first=False):
        from PIL import Image as PILImage
        p=parent.paragraphs[0] if first and parent.paragraphs else parent.add_paragraph()
        p.paragraph_format.space_after=Pt(4)
        if content:
            try:
                with PILImage.open(BytesIO(content)) as im:iw,ih=im.size
                scale=min(w/iw,h/ih)
                p.add_run().add_picture(BytesIO(content),width=Inches(iw*scale),height=Inches(ih*scale))
                return
            except Exception:pass
        p.add_run(placeholder).font.color.rgb=RGBColor.from_string('66757A')
        p.paragraph_format.space_before=Pt(h*20);p.paragraph_format.space_after=Pt(h*20)
    header=table(doc,[5.05,2.16]);left,right=header.rows[0].cells
    image(left,data['logo'],1.5,.46,'Propify',first=True)
    label(right,'Preparado por:',first=True);text(right,data['author'],size=9)
    title=doc.add_paragraph('Análisis comparativo de mercado',style='Title');title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p=text(doc,'Información aproximada al '+_fecha_larga(data['date']),size=8,color='66757A');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after=Pt(14)
    hero=table(doc,[3.35,3.86]);left,right=hero.rows[0].cells
    label(left,'Ubicación',first=True);text(left,data['address'],size=9)
    label(left,'Tipo de propiedad');text(left,params.get('property_type','Casa'),bold=True,size=10)
    facts=table(right,[1.2,1.28,1.38])
    for cell,(caption,value) in zip(facts.rows[0].cells,[('Área de terreno',_number(params.get('land'),2,' m²') if params.get('land') else 'No aplica'),('Área construida',_number(params.get('built'),2,' m²') if params.get('built') else 'No aplica'),('Antigüedad',age(params.get('age')))]):
        label(cell,caption,first=True);text(cell,value,bold=True,size=9)
    pdm=data.get('pdm')
    if pdm:
        doc.add_heading('Zona de uso PDM',level=1)
        text(doc,f"{pdm['codigo']} · {pdm['nombre']} · {pdm['categoria']} · Uso analizado: {pdm['property_type']}",bold=True,size=9)
        if pdm['rows']:
            columns=1+len(pdm['typologies']);label_width=1.55;value_width=(width-label_width)/max(1,columns-1)
            table_pdm=table(doc,[label_width]+[value_width]*(columns-1))
            for cell,value in zip(table_pdm.rows[0].cells,['Parámetro']+pdm['typologies']):
                label(cell,value,first=True)
            for item in pdm['rows']:
                cells=table_pdm.add_row().cells
                text(cells[0],item['label'],bold=True,size=7)
                for cell,value in zip(cells[1:],item['values']):text(cell,value,size=7)
        if pdm['compatible_uses']:text(doc,'Usos compatibles: '+pdm['compatible_uses'],size=7)
        for note in pdm['notes']:text(doc,note,size=7,color='66757A')
    doc.add_heading('Ubicación de las propiedades',level=1)
    location=table(doc,[3.62,3.59]);left,right=location.rows[0].cells
    image(left,data['map'],3.4,1.95,'Mapa no disponible',first=True)
    label(left,'P  Propiedad sujeto  ·  Números: propiedades seleccionadas')
    if data['croquis']:label(left,'Croquis referencial de distancias; no representa un mapa de calles.')
    label(right,'PRECIO PROMEDIO DE VENTA POR M2',first=True);text(right,_money(data['average'])+' /m²',bold=True,size=10)
    image(right,data['chart'],3.4,1.72,'Sin valores unitarios disponibles')
    for heading,rows in data['groups']:
        doc.add_heading(heading.capitalize(),level=1)
        columns=5;cell_width=width/columns
        for offset in range(0,len(rows),columns):
            cards=table(doc,[cell_width]*columns)
            for cell,row in zip(cards.rows[0].cells,rows[offset:offset+columns]):
                image(cell,data['photos'].get(row['id']),cell_width-.08,.64,first=True)
                text(cell,str(data['rows'].index(row)+1)+'. '+_clean(row.get('kind'),'Inmueble'),bold=True,size=8)
                text(cell,'Terreno '+_number(row.get('land'),2,' m²')+' · Construcción '+_number(row.get('built'),2,' m²'),size=7)
                text(cell,'Antigüedad: '+age(row.get('age')),size=7)
                text(cell,_clean(row.get('district') or row.get('title'),'Sin ubicación informada'),size=7)
                rental='alquil' in str(row.get('operation','')).lower()
                label(cell,'Precio de alquiler mensual' if rental else 'Precio de venta')
                text(cell,_money(row.get('price')),bold=True,size=8)
                text(cell,_money(_unit_price(row))+' /m²'+(' al mes' if rental else ''),size=7)
    doc.add_heading('Resultados',level=1)
    results=table(doc,[3.35,3.86]);left,right=results.rows[0].cells
    summary=text(left,data['summary'],size=9,first=True)
    summary.paragraph_format.right_indent=Pt(10)
    if data['values']:
        for i,(caption,key) in enumerate(RESULT_LABELS):
            label(right,caption,first=i==0);text(right,_money(data['values'][key]),bold=True,size=11)
    else:text(right,'No se obtuvo una estimación final porque faltaron comparables aptos.',first=True)
    if data['notes']:
        doc.add_heading('Justificación u observaciones',level=1)
        doc.add_paragraph(data['notes'])
    footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run('www.propify.pe').font.size=Pt(8)
    # Keep the editable Word body free of portal URLs, internal codes and metadata.
    _fit_one_page(doc)
    stream=BytesIO();doc.save(stream)
    return stream.getvalue()
