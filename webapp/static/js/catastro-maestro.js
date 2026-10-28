/* Common WGS84 geometry, source namespaces and a single vector canvas. */
(() => {
    'use strict';
    const world = ([lng,lat]) => {
        const sin=Math.sin(Math.max(-85,Math.min(85,lat))*Math.PI/180);
        return [(lng+180)/360*256,(.5-Math.log((1+sin)/(1-sin))/(4*Math.PI))*256];
    };
    function ringContains(point,ring) {
        let inside=false;
        for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
            const a=ring[i],b=ring[j];
            if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
        }
        return inside;
    }
    function contains(geometry,point) {
        const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
        return polygons.some(rings=>ringContains(point,rings[0])&&!rings.slice(1).some(r=>ringContains(point,r)));
    }
    function record(feature,source,key) {
        const geometry=feature.geometry;
        if(!['Polygon','MultiPolygon','LineString','MultiLineString'].includes(geometry?.type))return null;
        if(['LineString','MultiLineString'].includes(geometry.type)){
            const lines=geometry.type==='LineString'?[geometry.coordinates]:geometry.coordinates;
            const paths=lines.map(line=>line.map(world));
            const points=paths.flat(),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
            const path=paths.map(line=>line.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join('')).join('');
            return {feature,source,key,rings:paths,path,bbox:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]};
        }
        const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
        const rings=polygons.flat().map(ring=>ring.map(world));
        const points=rings.flat(),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
        const path=rings.map(ring=>ring.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join('')+'Z').join('');
        return {feature,source,key,rings,path,bbox:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]};
    }
    // IDs are qualified by source. A PDF geometry ID never becomes ID_LOTE.
    const recordId=(source,key,feature)=>source.id+':'+key+':'+feature.id;
    window.CatastroMasterGeometry={world,contains,record,recordId};
    if(typeof document==='undefined')return;
    const el=id=>document.getElementById('master-'+id);
    if(!el('workspace'))return;
    const fmt=n=>n.toLocaleString('es-PE');
    let map,vectorLayer,catalog,district,controller,selected=null,selectedFeature=null,detailRequest=0;
    let cataloguePromise=null;
    const collections=new Map(),enabled=new Map(),pending=new Map();
    const dataFeatures=new Map();
    const parkFeatures=new Map();
    const layerOn={manzanas:true,lotes:true,vias:true};
    const ALL_DISTRICTS='all';
    const masterRole=source=>source.role==='draft'||source.role==='snapshot';
    const districtLabel=code=>code===ALL_DISTRICTS?'Todos los distritos D1':
        (catalog?.districts.find(d=>d.ubigeo===code)?.name||code||'Sin distrito');
    const sourceDistrict=source=>source.ubigeo||source.districts?.[0]||district;
    const scoped=()=>[...collections.values()].filter(c=>district===ALL_DISTRICTS||c.district===district);
    const caymaRequested=()=>new URL(location.href).searchParams.get('cayma')==='1';
    const status=(text,error=false)=>{el('status').textContent=text;el('status').dataset.error=String(error);};
    let parkMode=false,parkToken='',parkSaved=new Set(),parkDraft=new Set();
    let loadTotal=0,loadDone=0;
    const isUuid=value=>/^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(String(value||''));
    const displayEntityId=(kind,id)=>isUuid(id)?((kind==='manzana'?'MANZANA-CM-':'LOTE-CM-')+String(id).replaceAll('-','').slice(0,12).toUpperCase()):null;
    const valueText=value=>value==null||value===''?'—':typeof value==='boolean'?(value?'Sí':'No'):typeof value==='object'?JSON.stringify(value):String(value);
    const attributeLabels={
        country_code:'País',ubigeo:'UBIGEO',postal_code:'Código postal',department:'Departamento',province:'Provincia',district:'Distrito',zone:'Zona',sector:'Sector',urbanization:'Urbanización / habilitación',block:'Manzana',lot:'Lote',building:'Edificación',entrance:'Ingreso',floor:'Piso',unit:'Unidad',address:'Dirección',address_block:'Manzana de dirección',address_lot:'Lote de dirección',street_type:'Tipo de vía',street_name:'Nombre de vía',municipal_number:'Número municipal',condition:'Condición',registry_office:'Oficina registral',registry_entry_type:'Tipo de partida',registry_entry_number:'Partida registral',registry_folios:'Fojas',registry_seat:'Asiento',notary_name:'Notaría',notary_kardex:'Kárdex',deed_date:'Fecha de escritura',property_registration_date:'Inscripción del predio',construction_declaration:'Declaración de fábrica',construction_registration_seat:'Asiento de fábrica',construction_registration_date:'Inscripción de fábrica',cuc:'CUC',cadastral_reference:'Referencia catastral',cadastral_use:'Uso catastral',observed_use:'Uso observado',zoning:'Zonificación',use_category:'Categoría de uso',business_category:'Giro',business_subcategory:'Subgiro',ciiu_code:'CIIU',ciiu_version:'Versión CIIU',commercial_name:'Nombre comercial',land_area:'Área de terreno documental',built_area:'Área construida documental',geometric_land_area:'Área geométrica',gis_land_area:'Área SIG de terreno (valor de fuente)',gis_built_area:'Área SIG construida (valor de fuente)',front:'Frente',back:'Fondo',left:'Izquierda',right:'Derecha',perimeter:'Perímetro',bedrooms:'Dormitorios',bathrooms:'Baños',half_bathrooms:'Medios baños',parking_spaces:'Estacionamientos',floors:'Pisos',units:'Unidades',is_corner:'Esquina',is_through:'Pasaje',faces_park:'Frente a parque'
    };
    const parkStatus=(text,error=false)=>{const node=el('park-status');if(!node)return;node.textContent=text;node.dataset.error=String(error);};
    function loading(text,done,total){
        const host=el('load-modal'),title=el('load-title'),bar=el('load-bar'),
            label=el('load-text'),percent=el('load-percent');
        if(!host)return;
        if(done==null){
            host.hidden=true;return;
        }
        host.hidden=false;
        const value=Math.max(0,Math.min(1,(done||0)/(total||1)));
        if(title)title.textContent='Cargando Catastro Maestro';
        if(bar)bar.value=value;
        if(percent)percent.textContent=Math.round(value*100)+'%';
        if(label)label.textContent=text;
    }
    const parkKey=(feature,source)=>{
        const value=String(feature?.properties?.ID_LOTE||'').trim();
        return /^\d{14}$/.test(value)?value:source.id+':'+String(feature.id);
    };
    const parkDirty=()=>parkSaved.size!==parkDraft.size||[...parkSaved].some(value=>!parkDraft.has(value));
    function refreshParkStyles(){
        for(const feature of dataFeatures.values())vectorLayer?.revertStyle(feature);
        for(const [key,feature] of parkFeatures){
            if(parkSaved.has(key)||parkDraft.has(key))vectorLayer?.overrideStyle(feature,{
                fillColor:'#54d48a',fillOpacity:.42,strokeColor:'#b8ffd4',strokeWeight:2.4,zIndex:4
            });
        }
        if(selectedFeature)vectorLayer?.overrideStyle(selectedFeature,{
            visible:true,fillColor:'#ffff55',fillOpacity:.24,strokeColor:'#ffffff',
            strokeOpacity:1,strokeWeight:3,clickable:true,zIndex:5
        });
    }
    function parkControls(){
        const concrete=district&&district!==ALL_DISTRICTS;
        if(el('park-search'))el('park-search').disabled=!concrete;
        if(el('park-save'))el('park-save').disabled=!concrete||!parkDirty();
        if(el('park-cancel'))el('park-cancel').disabled=!concrete||!parkDirty();
        if(el('park-search'))el('park-search').textContent=parkMode?'Terminar selección':'Buscar parques';
    }
    async function loadParkLots(){
        parkMode=false;parkToken='';parkSaved=new Set();parkDraft=new Set();
        parkControls();refreshParkStyles();
        if(!district||district===ALL_DISTRICTS){
            parkStatus('Selecciona un distrito concreto para editar parques.');
            return;
        }
        parkStatus('Consultando parques marcados…');
        try{
            const response=await fetch('/catastro/api/maestro/parques/?ubigeo='+encodeURIComponent(district),
                {credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
            const value=await response.json();
            if(!response.ok)throw Error(value.error||'No se pudieron cargar los parques.');
            parkToken=value.token||'';
            parkSaved=new Set(value.lots||[]);
            parkDraft=new Set(parkSaved);
            parkStatus(value.lots?.length?fmt(value.lots.length)+' lotes marcados como parque.':'Todavía no hay lotes marcados como parque.');
            refreshParkStyles();
        }catch(error){parkStatus(error.message,true);}
        parkControls();
    }
    function visible() {
        return scoped().filter(c=>enabled.get(c.source.id)&&layerOn[c.key]);
    }
    function counts() {
        for(const key of ['manzanas','lotes','vias']) {
            const n=visible().filter(c=>c.key===key).reduce((sum,c)=>sum+c.records.length,0);
            el('count-'+key).textContent=fmt(n);
        }
        el('map-note').textContent=!visible().length?'Sin registros maestros visibles en el ámbito seleccionado.':district===ALL_DISTRICTS
            ?'Catastro Maestro · todos los distritos con registros D1 · procedencia conservada por entidad.'
            :'Catastro Maestro · registros vinculados por UUID; cada campo conserva su fuente y versión.';
    }
    function fit() {
        if(!map)return;
        const bounds=new google.maps.LatLngBounds();
        visible().forEach(c=>c.records.forEach(r=>{
            const parts=r.feature.geometry.type==='Polygon'?[r.feature.geometry.coordinates]:r.feature.geometry.coordinates;
            parts.forEach(p=>p[0].forEach(([lng,lat])=>bounds.extend({lat,lng})));
        }));
        if(!bounds.isEmpty())map.fitBounds(bounds,35);
        else if(district!==ALL_DISTRICTS){const center=catalog?.districts.find(d=>d.ubigeo===district)?.center;if(center){map.setCenter(center);map.setZoom(15);}}
    }
    function openDetailCard(title) {
        const card=el('detail-card'),heading=el('detail-title');
        if(heading)heading.textContent=title;
        if(card)card.hidden=false;
    }
    function closeDetailCard(deselect=true) {
        ++detailRequest;
        const card=el('detail-card');
        if(card)card.hidden=true;
        if(deselect){
            if(selectedFeature)vectorLayer?.revertStyle(selectedFeature);
            selected=null;selectedFeature=null;
        }
        const host=el('detail');
        if(host)host.replaceChildren(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Selecciona un contorno para ver su ficha completa.'}));
    }
    function detail(item) {
        const panel=el('detail');panel.replaceChildren();
        const itemDistrict=sourceDistrict(item.source);
        openDetailCard(item.key==='lotes'?'Ficha del lote':item.key==='vias'?'Ficha de la vía':'Ficha de la manzana');
        if(district===ALL_DISTRICTS&&/^\d{6}$/.test(itemDistrict||''))
            window.dispatchEvent(new CustomEvent('catastro-master-raster-focus',{detail:{ubigeo:itemDistrict}}));
        const p=item.feature.properties,dl=document.createElement('dl');
        dl.className='master-basic-grid';
        const entityKind=item.key==='manzanas'?'manzana':'lote';
        const values=item.key==='vias'?[
            ['Distrito',p.DISTRICT_NAME||districtLabel(itemDistrict)],
            ['Fuente',item.source.name],
            ['Tipo de vía',p.TIPO_VIA||p.TIP_VIA||'Sin dato'],
            ['Nombre de vía',p.NOM_VIA||'Sin nombre'],
            ['Código de vía',p.COD_VIA||'Sin dato']]:[
            ['Distrito',p.DISTRICT_NAME||districtLabel(itemDistrict)],
            ['Fuente',item.source.name],['Manzana',p.COD_MZNA||'Sin numeración en la fuente']];
        if(item.key==='lotes')values.push(['Lote',p.COD_LOTE||'Sin numeración en la fuente']);
        values.push(['Código catastral',p.ID_LOTE||p.ID_MZNA||'No disponible'],
            ['ID Maestro',isUuid(p.ELEMENT_ID)?p.ELEMENT_ID:recordId(item.source,item.key,item.feature)]);
        if(displayEntityId(entityKind,p.ELEMENT_ID))values.push(['Alias de pantalla',displayEntityId(entityKind,p.ELEMENT_ID)]);
        if(p.BLOCK_REF)values.push(['Manzana vinculada (ID interno)',p.BLOCK_REF]);
        if(item.source.role==='draft')values.push(['Vinculación','Consultando identidades del maestro…'],['Versión geométrica',p.GEOMETRY_VERSION_ID||'Sin dato']);
        else if(item.source.role==='snapshot')values.push(['Estado','Vector extraído y conservado en el Catastro Maestro'],['Ficha maestra','Pendiente de vincular; no impide mostrar la geometría']);
        else if(item.source.reference_only)values.push(['Estado','Contorno recuperado; pendiente de contraste con otros mapas'],
            ['Fecha del plano','Agosto de 2006'],['Ubicación','PSAD56 / UTM 19S inferido; transformado a WGS84']);
        for(const [label,value] of values){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;dl.append(dt,dd);}
        panel.append(dl);
        const details=document.createElement('div');details.className='master-entity-data';details.setAttribute('aria-live','polite');panel.append(details);
        if(item.key==='lotes'&&/^\d{14}$/.test(String(p.ID_LOTE||''))){
            dl.hidden=true;
            details.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Cargando fachada, titulares, fichas y procedencia desde el Catastro Maestro…'}));
            loadLotDossier(item,String(p.ID_LOTE),details);
        }
        else if(item.source.role==='draft'&&isUuid(p.ELEMENT_ID))loadEntityDetail(item,p.ELEMENT_ID,details);
        else if(item.source.role!=='draft')details.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Esta fuente es de referencia. Para ver la ficha completa debe estar vinculada como Registro Maestro de Lote.'}));
    }
    function addEntitySection(host,title,content,className='') {
        const section=document.createElement('section');section.className='master-entity-section '+className;
        const heading=document.createElement('h3');heading.textContent=title;section.append(heading,content);host.append(section);
        return section;
    }
    function addEntityValues(host,title,values,empty='Sin datos',className='',options={}) {
        const source=values||{};
        const rows=(options.all?options.keys||Object.keys(source):Object.entries(source))
            .map(key=>Array.isArray(key)?[key[0],source[key[0]]]:[key,source[key]]);
        const box=document.createElement('dl');box.className='master-entity-grid';
        if(!rows.length){const p=document.createElement('p');p.className='master-help';p.textContent=empty;return addEntitySection(host,title,p,className);}
        rows.forEach(([key,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=attributeLabels[key]||key.replaceAll('_',' ');dd.textContent=value==null||value===''?'Sin dato':valueText(value);box.append(dt,dd);});
        return addEntitySection(host,title,box,className);
    }
    function renderDossierFlat(data,item,host,request) {
        if(request!==detailRequest)return;
        host.replaceChildren();
        const statusBox=document.createElement('p');statusBox.className='master-link-status';
        statusBox.textContent=data.master_status==='normalized_d1'
            ?'Catastro Maestro · D1 · identidad normalizada'
            :'Catastro Maestro · archivo durable · normalización D1 pendiente';
        host.append(statusBox);
        if(data.d1_warning)host.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'D1 no respondió en esta consulta; se muestra la capa archivada del maestro. '+data.d1_warning}));
        const links=data.identity_links||[];
        if(links.length){
            const linked=document.createElement('div');linked.className='master-identity-links';
            for(const link of links){const row=document.createElement('div');row.append(Object.assign(document.createElement('code'),{textContent:link.source_feature_id}),Object.assign(document.createElement('span'),{textContent:(link.layer||'')+' · '+(link.source_name||link.source_id||'')+' · '+(link.version_label||link.version_id||'')}));linked.append(row);}
            addEntitySection(host,'Identidad y procedencia',linked);
        }
        const attributes={...(data.attributes||{})};
        attributes.district=attributes.district||districtLabel(sourceDistrict(item.source));
        const shown=new Set(['district','ubigeo','sector','block','lot','address','street_type','street_name','municipal_number','cadastral_reference','cuc','land_area','built_area','gis_land_area','gis_built_area','perimeter','front','back','left','right','floors','units','is_corner','is_through','faces_park','condition','cadastral_use','observed_use','zoning']);
        addEntityValues(host,'Ubicación e identificación',attributes,'Sin dato','', {all:true,
            keys:['district','ubigeo','sector','block','lot','address','street_type','street_name','municipal_number','cadastral_reference','cuc']});
        addEntityValues(host,'Áreas y perímetro',attributes,'Sin dato','', {all:true,
            keys:['land_area','built_area','gis_land_area','gis_built_area','perimeter','front','back','left','right']});
        addEntityValues(host,'Características del lote',attributes,'Sin dato','', {all:true,
            keys:['floors','units','is_corner','is_through','faces_park','condition','cadastral_use','observed_use','zoning']});
        const other=Object.fromEntries(Object.entries(attributes).filter(([key])=>!shown.has(key)));
        if(Object.keys(other).length)addEntityValues(host,'Otros campos extraídos',other,'Sin otros campos extraídos.');
        const documentsByRecord=new Map();
        for(const media of data.media||[]){const record=media.details?.source_record_id||media.record_id||media.source_record_id;if(!record)continue;if(!documentsByRecord.has(record))documentsByRecord.set(record,[]);documentsByRecord.get(record).push(media);}
        const units=document.createElement('div');units.className='master-entity-list';
        const unitRows=data.unit_attributes||data.units||[];
        if(unitRows.length){
            for(const unit of unitRows){
                const record=String(unit.source_feature_id||unit.record_id||'');
                const row=document.createElement('article');
                row.append(Object.assign(document.createElement('strong'),{textContent:'Unidad / ficha '+record}));
                row.append(Object.assign(document.createElement('small'),{textContent:[
                    unit.land_area!=null?'Área terreno '+valueText(unit.land_area)+' m²':null,
                    unit.built_area!=null?'Área construida '+valueText(unit.built_area)+' m²':null,
                    unit.floors!=null?'Pisos '+valueText(unit.floors):null,
                    unit.cadastral_year!=null?'Año '+valueText(unit.cadastral_year):null
                ].filter(Boolean).join(' · ')||'Campos extraídos sin medidas normalizadas'}));
                const links=document.createElement('span');links.className='master-unit-links';
                for(const doc of documentsByRecord.get(record)||[]){if(!doc.url)continue;const link=document.createElement('a');link.href=doc.url;link.target='_blank';link.rel='noopener';link.textContent=doc.kind==='individual_record_pdf'?'Abrir ficha individual':doc.kind==='cadastral_report_pdf'?'Abrir reporte catastral':(doc.kind||'Abrir documento');links.append(link);}
                row.append(links);units.append(row);
            }
        }else units.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin unidades o fichas documentales vinculadas.'}));
        addEntitySection(host,'Unidades y fichas registrales',units);
        const owners=document.createElement('div');owners.className='master-entity-list';
        if((data.owners||[]).length){for(const owner of data.owners){const row=document.createElement('article');row.append(Object.assign(document.createElement('strong'),{textContent:owner.name||'Titular sin nombre'}),Object.assign(document.createElement('small'),{textContent:[owner.document_type,owner.document_number,owner.kind,owner.share!=null?owner.share+'%':null,owner.condition].filter(Boolean).join(' · ')}));owners.append(row);}}
        else owners.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin titulares documentados en la capa extraída.'}));
        addEntitySection(host,'Titulares y derechos',owners);
        const galleryItems=data.gallery||[];
        const gallery=document.createElement('div');gallery.className='master-lot-gallery';
        for(const imageItem of galleryItems){if(!imageItem.url)continue;const link=document.createElement('a');link.href=imageItem.url;link.target='_blank';link.rel='noopener';const image=document.createElement('img');image.loading='lazy';image.alt='Fotografía catastral del lote '+data.lot_id;image.src=imageItem.url;link.append(image);gallery.append(link);}
        if(!galleryItems.length)gallery.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin fotografías catastrales archivadas en esta capa.'}));
        addEntitySection(host,'Galería de imágenes',gallery);
        const mediaBox=document.createElement('div');mediaBox.className='master-entity-list';
        if((data.media||[]).length){for(const media of data.media){if(!media.url)continue;const row=document.createElement('article');const link=document.createElement('a');link.href=media.url;link.target='_blank';link.rel='noopener';const kind=String(media.kind||'').toLowerCase();if(/facade|photo|image|foto/.test(kind)){const image=document.createElement('img');image.loading='lazy';image.alt=media.kind||'Fotografía del lote';image.src=media.url;link.append(image);}link.append(document.createTextNode(media.kind||media.filename||'Archivo'));row.append(link,Object.assign(document.createElement('small'),{textContent:[media.filename,media.observed_at,media.sha256&&('SHA-256 '+media.sha256.slice(0,12)+'…')].filter(Boolean).join(' · ')}));mediaBox.append(row);}}
        else mediaBox.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin fotografías ni documentos vinculados.'}));
        addEntitySection(host,'Fotografías y documentos',mediaBox);
        const catalog=data.catalog||{};
        if((catalog.identifiers||[]).length)addEntityValues(host,'Identificadores externos',Object.fromEntries(catalog.identifiers.map((row,index)=>[(row.scheme+' · '+(row.authority||'sin autoridad'))+(index?' #'+(index+1):''),row.value])),'Sin identificadores externos.');
        if((catalog.addresses||[]).length){const box=document.createElement('div');box.className='master-entity-list';for(const address of catalog.addresses){const row=document.createElement('article');row.append(Object.assign(document.createElement('strong'),{textContent:address.full_address||'Dirección sin texto'}),Object.assign(document.createElement('small'),{textContent:[address.address_type,address.precision,address.status].filter(Boolean).join(' · ')}));box.append(row);}addEntitySection(host,'Direcciones',box);}
        if((data.registral_acts||[]).length)addEntitySection(host,'Actos registrales',Object.assign(document.createElement('pre'),{className:'master-entity-json',textContent:JSON.stringify(data.registral_acts,null,2)}));
        if(data.missing?.length)addEntitySection(host,'Datos faltantes en la fuente',Object.assign(document.createElement('p'),{className:'master-help',textContent:data.missing.join(' · ')}));
        addEntityValues(host,'Cobertura del registro',{campos_con_valor:Object.values(attributes).filter(value=>value!==null&&value!==undefined&&value!=='').length,unidades:unitRows.length,titulares:(data.owners||[]).length,medios:(data.media||[]).length,evidencias:Object.keys(data.provenance||{}).length},'Sin métricas de cobertura.','master-entity-metrics');
    }
    function addEntityRows(host,title,rows,empty='Sin datos') {
        const box=document.createElement('dl');box.className='master-entity-grid';
        if(!rows.length){const p=document.createElement('p');p.className='master-help';p.textContent=empty;return addEntitySection(host,title,p);}
        rows.forEach(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value==null||value===''?'Sin dato':valueText(value);box.append(dt,dd);});
        return addEntitySection(host,title,box);
    }
    function addEntityColumnGroups(host,title,groups) {
        const box=document.createElement('div');box.className='master-entity-columns';
        for(const rows of groups){
            const stack=document.createElement('dl');stack.className='master-entity-stack';
            rows.forEach(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value==null||value===''?'Sin dato':valueText(value);stack.append(dt,dd);});
            box.append(stack);
        }
        return addEntitySection(host,title,box);
    }
    function renderDossier(data,item,host,request) {
        if(request!==detailRequest)return;
        host.replaceChildren();
        const attributes={...(data.attributes||{})};
        attributes.district=attributes.district||districtLabel(sourceDistrict(item.source));
        const media=data.media||[],unitRows=data.unit_attributes||data.units||[];
        const selectedRecord=data.selected_record_id||unitRows[0]?.source_feature_id||unitRows[0]?.record_id||'';
        const selectedUnit=unitRows.find(unit=>String(unit.source_feature_id||unit.record_id||'')===String(selectedRecord))||unitRows[0]||{};
        const measureValues={...attributes,...selectedUnit};
        const galleryItems=[...new Map([...(data.gallery||[]),...media.filter(entry=>/facade|photo|image|foto/i.test(String(entry.kind||'')))].filter(entry=>entry.url).map(entry=>[entry.url,entry])).values()];
        const hero=document.createElement('section');hero.className='master-dossier-hero';
        const emptyHero=document.createElement('div');emptyHero.className='master-dossier-hero-empty';emptyHero.textContent='Sin fotografía de fachada publicada en el Catastro Maestro';hero.append(emptyHero);
        if(galleryItems[0]){
            const photo=document.createElement('img');photo.loading='eager';photo.alt='Fotografía de fachada del lote '+data.lot_id;
            photo.addEventListener('error',()=>photo.remove());photo.src=galleryItems[0].url;hero.prepend(photo);
        }
        const heroCopy=document.createElement('div');heroCopy.className='master-dossier-hero-copy';
        const heroTitle=document.createElement('h2');heroTitle.textContent='Lote '+(attributes.lot||item.feature?.properties?.COD_LOTE||data.lot_id.slice(-3));
        const heroLine=document.createElement('p');heroLine.textContent=[attributes.district||districtLabel(sourceDistrict(item.source)),attributes.sector&&('Sector '+attributes.sector),attributes.block&&('Mz. '+attributes.block),'Lote '+(attributes.lot||data.lot_id.slice(-3))].filter(Boolean).join(' · ');
        heroCopy.append(heroTitle,heroLine);hero.append(heroCopy);host.append(hero);
        const tabList=document.createElement('div');tabList.className='master-dossier-tabs';tabList.setAttribute('role','tablist');tabList.setAttribute('aria-label','Información del lote');
        const panelHost=document.createElement('div');panelHost.className='master-dossier-panels';host.append(tabList,panelHost);
        const tabs=[];
        function activate(button){
            for(const tab of tabs){const current=tab.button===button;tab.button.setAttribute('aria-selected',String(current));tab.button.tabIndex=current?0:-1;tab.panel.hidden=!current;}
        }
        function addTab(key,label,count=0){
            const id='master-dossier-tab-'+key,panelId=id+'-panel';
            const button=document.createElement('button');button.type='button';button.className='master-dossier-tab';button.id=id;button.setAttribute('role','tab');button.setAttribute('aria-controls',panelId);button.setAttribute('aria-selected','false');button.tabIndex=-1;
            button.append(document.createTextNode(label));if(count)button.append(Object.assign(document.createElement('small'),{textContent:fmt(count)}));
            const panel=document.createElement('section');panel.className='master-dossier-panel';panel.id=panelId;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',id);panel.hidden=true;
            tabList.append(button);panelHost.append(panel);tabs.push({button,panel});button.addEventListener('click',()=>activate(button));return panel;
        }
        tabList.addEventListener('keydown',event=>{
            if(!['ArrowLeft','ArrowRight'].includes(event.key))return;
            const index=tabs.findIndex(tab=>tab.button===document.activeElement);if(index<0)return;
            event.preventDefault();const next=(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;activate(tabs[next].button);tabs[next].button.focus();
        });
        const summary=addTab('resumen','Resumen');
        if(data.d1_warning)summary.append(Object.assign(document.createElement('p'),{className:'master-dossier-note',textContent:'D1 no respondió; se muestra la capa archivada del maestro.'}));
        const masterId=data.master?.entity_id||'';
        const measured=(value,suffix='')=>value==null||value===''?'Sin dato':valueText(value)+suffix;
        addEntityRows(summary,'Ubicación catastral',[
            ['Distrito',attributes.district||districtLabel(sourceDistrict(item.source))],
            ['Urbanización',attributes.urbanization],
            ['Manzana / Lote',[attributes.block||item.feature?.properties?.COD_MZNA,attributes.lot||item.feature?.properties?.COD_LOTE].map(value=>value==null||value===''?'Sin dato':value).join(' / ')],
            ['Vía',[attributes.street_type,attributes.street_name].filter(Boolean).join(' ')||attributes.address],
        ]);
        addEntityColumnGroups(summary,'Características',[
            [['Pisos',attributes.floors],['Unidades',attributes.units]],
            [['Esquina',attributes.is_corner],['Frente a parque',attributes.faces_park]],
        ]);
        addEntityColumnGroups(summary,'Áreas principales',[
            [['Terreno',measured(measureValues.land_area,' m²')],['Terreno SIG',measured(measureValues.gis_land_area,' m²')]],
            [['Construida',measured(measureValues.built_area,' m²')],['Construida SIG',measured(measureValues.gis_built_area,' m²')]],
        ]);
        addEntityRows(summary,'Perímetros',[
            ['Perímetro total',measured(measureValues.perimeter,' m')],
            ['Frente',measured(measureValues.front,' m')],
            ['Derecha',measured(measureValues.right,' m')],
            ['Izquierda',measured(measureValues.left,' m')],
            ['Fondo',measured(measureValues.back,' m')],
        ]);
        const shown=new Set(['district','ubigeo','sector','block','lot','address','street_type','street_name','municipal_number','urbanization','postal_code','cadastral_reference','cuc','land_area','built_area','gis_land_area','gis_built_area','perimeter','front','back','left','right','floors','units','is_corner','is_through','faces_park','condition','cadastral_use','observed_use','zoning']);
        const catalog=data.catalog||{};
        const measures=addTab('medidas','Medidas');
        addEntityValues(measures,'Áreas del lote',measureValues,'Sin dato','', {all:true,
            keys:['land_area','built_area','gis_land_area','gis_built_area','geometric_land_area']});
        addEntityValues(measures,'Perímetro y linderos',measureValues,'Sin dato','', {all:true,
            keys:['perimeter','front','right','left','back']});
        if(unitRows.length>1)addEntityValues(measures,'Unidad seleccionada',selectedUnit,'Sin medidas de unidad.');
        const ownersPanel=addTab('titulares','Titulares',(data.owners||[]).length);
        const owners=document.createElement('div');owners.className='master-entity-list';
        if((data.owners||[]).length){
            for(const owner of data.owners){const row=document.createElement('article');row.append(Object.assign(document.createElement('strong'),{textContent:owner.name||'Titular sin nombre'}),Object.assign(document.createElement('small'),{textContent:[owner.document_type,owner.document_number,owner.kind,owner.share!=null?owner.share+'%':null,owner.condition].filter(Boolean).join(' · ')||'Sin documento o condición publicada'}));owners.append(row);}
        }else owners.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin titulares documentados en la capa extraída.'}));
        addEntitySection(ownersPanel,'Titulares y derechos',owners);
        const documentsPanel=addTab('documentos','Fichas',media.length);
        const documentsByRecord=new Map();
        for(const entry of media){const record=entry.details?.source_record_id||entry.record_id||entry.source_record_id;if(!record)continue;if(!documentsByRecord.has(record))documentsByRecord.set(record,[]);documentsByRecord.get(record).push(entry);}
        const unitList=document.createElement('div');unitList.className='master-entity-list';
        if(unitRows.length){
            for(const unit of unitRows){
                const record=String(unit.source_feature_id||unit.record_id||'');
                const row=document.createElement('article');
                row.append(Object.assign(document.createElement('strong'),{textContent:'Unidad / ficha '+record}));
                row.append(Object.assign(document.createElement('small'),{textContent:[
                    unit.land_area!=null?'Área terreno '+valueText(unit.land_area)+' m²':null,
                    unit.built_area!=null?'Área construida '+valueText(unit.built_area)+' m²':null,
                    unit.floors!=null?'Pisos '+valueText(unit.floors):null,
                    unit.cadastral_year!=null?'Año '+valueText(unit.cadastral_year):null
                ].filter(Boolean).join(' · ')||'Campos extraídos sin medidas normalizadas'}));
                const links=document.createElement('span');links.className='master-unit-links';
                for(const doc of documentsByRecord.get(record)||[]){if(!doc.url)continue;const link=document.createElement('a');link.href=doc.url;link.target='_blank';link.rel='noopener';link.textContent=doc.kind==='individual_record_pdf'?'Abrir ficha individual':doc.kind==='cadastral_report_pdf'?'Abrir reporte catastral':(doc.kind||'Abrir documento');links.append(link);}
                row.append(links);unitList.append(row);
            }
        }else unitList.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin unidades o fichas documentales vinculadas.'}));
        addEntitySection(documentsPanel,'Unidades y fichas registrales',unitList);
        const mediaBox=document.createElement('div');mediaBox.className='master-entity-list';
        const documentItems=media.filter(entry=>entry.url&&!/facade|photo|image|foto/i.test(String(entry.kind||'')));
        if(documentItems.length){for(const entry of documentItems){const row=document.createElement('article');const link=document.createElement('a');link.href=entry.url;link.target='_blank';link.rel='noopener';link.textContent=entry.kind==='individual_record_pdf'?'Abrir ficha individual':entry.kind==='cadastral_report_pdf'?'Abrir reporte catastral':(entry.filename||entry.kind||'Abrir documento');row.append(link,Object.assign(document.createElement('small'),{textContent:[entry.observed_at,entry.sha256&&('SHA-256 '+entry.sha256.slice(0,12)+'…')].filter(Boolean).join(' · ')}));mediaBox.append(row);}}
        else mediaBox.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin documentos vinculados.'}));
        addEntitySection(documentsPanel,'Documentos y originales',mediaBox);
        const galleryPanel=addTab('galeria','Galería',galleryItems.length);
        const gallery=document.createElement('div');gallery.className='master-lot-gallery';
        for(const imageItem of galleryItems){const link=document.createElement('a');link.href=imageItem.url;link.target='_blank';link.rel='noopener';const image=document.createElement('img');image.loading='lazy';image.alt='Fotografía catastral del lote '+data.lot_id;image.src=imageItem.url;link.append(image);gallery.append(link);}
        if(!galleryItems.length)gallery.append(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Sin fotografías catastrales archivadas en esta capa.'}));
        addEntitySection(galleryPanel,'Imágenes publicadas',gallery);
        const more=addTab('mas','Más datos');
        addEntityRows(more,'Identificación y publicación',[
            ['Código catastral',data.lot_id],
            ['ID maestro',masterId||'Sin vínculo D1'],
            ['Alias de pantalla',displayEntityId('lote',masterId)||'Sin alias'],
            ['Fuente',data.source_origin||item.source.name],
            ['Estado',data.master_status==='normalized_d1'?'Registro normalizado en D1':'Archivo pendiente de normalización D1'],
            ['Revisión maestra',data.master_revision],
        ]);
        addEntityValues(more,'Dirección',attributes,'Sin dato','', {all:true,
            keys:['address','municipal_number','postal_code','cadastral_reference','cuc']});
        addEntityValues(more,'Clasificación y condición',attributes,'Sin dato','', {all:true,
            keys:['cadastral_use','observed_use','zoning','condition','is_through']});
        const other=Object.fromEntries(Object.entries(attributes).filter(([key])=>!shown.has(key)));
        if(Object.keys(other).length)addEntityValues(more,'Otros campos extraídos',other,'Sin otros campos extraídos.');
        if((catalog.identifiers||[]).length)addEntityValues(more,'Identificadores externos',Object.fromEntries(catalog.identifiers.map((row,index)=>[(row.scheme+' · '+(row.authority||'sin autoridad'))+(index?' #'+(index+1):''),row.value])),'Sin identificadores externos.');
        const provenance=addTab('procedencia','Origen');
        const links=data.identity_links||[];
        if(links.length){const linked=document.createElement('div');linked.className='master-identity-links';for(const link of links){const row=document.createElement('div');row.append(Object.assign(document.createElement('code'),{textContent:link.source_feature_id}),Object.assign(document.createElement('span'),{textContent:(link.layer||'')+' · '+(link.source_name||link.source_id||'')+' · '+(link.version_label||link.version_id||'')}));linked.append(row);}addEntitySection(provenance,'Identidad y versión de origen',linked);}
        addEntityRows(provenance,'Trazabilidad',[
            ['Estado de publicación',data.master_status==='normalized_d1'?'Normalizado en D1':'Archivo durable pendiente de D1'],
            ['Revisión maestra',data.master_revision],
            ['Archivo de origen',data.source_manifest?.object_key],
            ['SHA-256 del archivo',data.source_manifest?.sha256],
            ['Fecha del archivo',data.source_manifest?.retrieved_at],
        ]);
        if(data.missing?.length)addEntitySection(provenance,'Datos faltantes en la fuente',Object.assign(document.createElement('p'),{className:'master-help',textContent:data.missing.join(' · ')}));
        if((data.registral_acts||[]).length)addEntitySection(provenance,'Actos registrales',Object.assign(document.createElement('pre'),{className:'master-dossier-raw',textContent:JSON.stringify(data.registral_acts,null,2)}));
        if(Object.keys(data.provenance||{}).length)addEntitySection(provenance,'Evidencia por campo',Object.assign(document.createElement('pre'),{className:'master-dossier-raw',textContent:JSON.stringify(data.provenance,null,2)}));
        addEntityValues(provenance,'Cobertura del registro',{campos_con_valor:Object.values(attributes).filter(value=>value!==null&&value!==undefined&&value!=='').length,unidades:unitRows.length,titulares:(data.owners||[]).length,medios:media.length,evidencias:Object.keys(data.provenance||{}).length},'Sin métricas de cobertura.','master-entity-metrics');
        activate(tabs[0].button);
    }
    async function loadLotDossier(item,lotId,host) {
        const request=++detailRequest;host.replaceChildren(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Cargando todas las capas del lote desde el Catastro Maestro…'}));
        try{
            const data=await json('/catastro/api/maestro/lotes/'+encodeURIComponent(lotId)+'/ficha/');
            renderDossier(data,item,host,request);
        }catch(error){if(request===detailRequest){host.replaceChildren(Object.assign(document.createElement('p'),{className:'master-help',textContent:error.message}));host.lastElementChild.dataset.error='true';}}
    }
    async function loadEntityDetail(item,entityId,host) {
        const request=++detailRequest;host.replaceChildren(Object.assign(document.createElement('p'),{className:'master-help',textContent:'Cargando ficha maestra, titulares, documentos y procedencia…'}));
        try{
            const data=await json('/catastro/api/maestro/composicion/?'+new URLSearchParams({view:'entity',id:entityId}));
            renderDossier({...data,master_status:'normalized_d1'},item,host,request);
        }catch(error){if(request===detailRequest){host.replaceChildren(Object.assign(document.createElement('p'),{className:'master-help',textContent:error.message}));host.lastElementChild.dataset.error='true';}}
    }
    function selectFeature(item,feature) {
        if(selectedFeature&&selectedFeature!==feature)vectorLayer.revertStyle(selectedFeature);
        selected=item;selectedFeature=feature;
        if(feature)vectorLayer.overrideStyle(feature,{
            visible:true,fillColor:'#ffff55',fillOpacity:.2,strokeColor:'#ffffff',
            strokeOpacity:1,strokeWeight:3,clickable:true
        });
        if(item)detail(item);else closeDetailCard(false);
    }
    function selectAt(point) {
        const target=world(point),matches=[];
        visible().forEach(c=>c.records.forEach(r=>{
            if(target[0]>=r.bbox[0]&&target[0]<=r.bbox[2]&&target[1]>=r.bbox[1]&&target[1]<=r.bbox[3]&&contains(r.feature.geometry,point))matches.push(r);
        }));
        matches.sort((a,b)=>{
            const priority=item=>item.source.role==='draft'?-1:0;
            return priority(a)-priority(b)||(a.key==='lotes'?0:1)-(b.key==='lotes'?0:1);
        });
        const item=matches[0]||null;
        selectFeature(item,item?dataFeatures.get(recordId(item.source,item.key,item.feature)):null);
    }
    function lotAt(point){
        const target=world(point),matches=[];
        visible().filter(c=>c.key==='lotes').forEach(c=>c.records.forEach(r=>{
            if(target[0]>=r.bbox[0]&&target[0]<=r.bbox[2]&&target[1]>=r.bbox[1]&&target[1]<=r.bbox[3]&&contains(r.feature.geometry,point))matches.push(r);
        }));
        matches.sort((a,b)=>(a.source.role==='draft'?-1:0)-(b.source.role==='draft'?-1:0));
        return matches[0]||null;
    }
    function toggleParkAt(point){
        const item=lotAt(point);
        if(!item){parkStatus('El punto seleccionado no está dentro de un lote.',true);return;}
        const key=parkKey(item.feature,item.source);
        if(!/^\d{14}$/.test(key)){parkStatus('El lote no tiene un código catastral válido para guardar.',true);return;}
        if(parkDraft.has(key))parkDraft.delete(key);else parkDraft.add(key);
        refreshParkStyles();parkControls();
        const p=item.feature.properties||{};
        parkStatus((parkDraft.has(key)?'Marcado':'Desmarcado')+' · sector '+valueText(p.COD_SECT)+
            ' · manzana '+valueText(p.COD_MZNA)+' · lote '+valueText(p.COD_LOTE)+
            ' · '+parkDraft.size+' seleccionados');
    }

    function vectorStyle(feature) {
        const key=feature.getProperty('MASTER_LAYER');
        const sourceId=feature.getProperty('SOURCE_ID');
        return {
            visible:Boolean((district===ALL_DISTRICTS||feature.getProperty('DISTRICT')===district)&&layerOn[key]&&enabled.get(sourceId)!==false),
            clickable:false,fillOpacity:0,
            strokeColor:key==='vias'?'#63b8ff':key==='manzanas'?'#06d7af':'#efb140',
            strokeOpacity:key==='vias'?.9:key==='manzanas'?.95:.8,
            strokeWeight:key==='vias'?2:key==='manzanas'?1.7:.8,
            zIndex:key==='vias'?3:key==='manzanas'?1:2,
        };
    }
    function makeVectorLayer() {
        vectorLayer=new google.maps.Data({map});
        vectorLayer.setStyle(vectorStyle);
    }
    function addVectorFeatures(collection) {
        return new Promise(resolve=>{
            let start=0;
            function drawNext(){
                const slice=collection.records.slice(start,start+2000);
                const features=slice.map(item=>{
                    const masterId=recordId(item.source,item.key,item.feature);
                    return {type:'Feature',properties:{MASTER_ID:masterId,MASTER_LAYER:item.key,
                        SOURCE_ID:item.source.id,DISTRICT:collection.district},
                        geometry:item.feature.geometry};
                });
                const added=vectorLayer.addGeoJson({type:'FeatureCollection',features},
                    {idPropertyName:'MASTER_ID'});
                added.forEach((feature,index)=>{
                    dataFeatures.set(feature.getProperty('MASTER_ID'),feature);
                    const item=slice[index];
                    if(item?.key==='lotes'){
                        const key=parkKey(item.feature,item.source);
                        if(/^\d{14}$/.test(key))parkFeatures.set(key,feature);
                    }
                });
                vectorLayer.setStyle(vectorStyle);
                refreshParkStyles();
                start+=slice.length;
                if(start<collection.records.length)setTimeout(drawNext,0);
                else resolve();
            }
            drawNext();
        });
    }
    async function json(url,signal,timeoutMs=45000) {
        const controller=new AbortController(),abort=()=>controller.abort();let timedOut=false;
        if(signal?.aborted)controller.abort();
        signal?.addEventListener('abort',abort,{once:true});
        const timer=setTimeout(()=>{timedOut=true;controller.abort();},timeoutMs);
        try{
            const response=await fetch(url,{credentials:'same-origin',signal:controller.signal,headers:{Accept:'application/json'}});
            if(!response.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para consultar el catastro.');
            const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo cargar la capa.');return result;
        }catch(error){
            if(timedOut)throw Error('La consulta tardó demasiado. Se reintentará automáticamente.');
            throw error;
        }finally{
            clearTimeout(timer);signal?.removeEventListener('abort',abort);
        }
    }
    async function snapshotJson(url,signal){
        try{
            return await json(url,signal,45000);
        }catch(error){
            if(signal?.aborted||error.name==='AbortError')throw error;
            await new Promise(resolve=>setTimeout(resolve,300));
            return json(url,signal,60000);
        }
    }
    async function loadSource(source,signal) {
        const scope=district;
        const current=scope===ALL_DISTRICTS?sourceDistrict(source):scope;
        const client=source.transport==='arcgis'?window.GeollaqtaDistrict.create():null;
        for(const key of ['manzanas','lotes','vias']) {
            if(!Number(source.layers?.[key]?.count||0))continue;
            const id=current+':'+source.id+':'+key;
            if(collections.has(id))continue;
            let task=pending.get(id);
            if(task){
                try{await task;}catch(error){if(error.name!=='AbortError')throw error;}
                if(signal.aborted)return;
                if(collections.has(id))continue;
            }
            {
                task=(async()=>{
                    let collection;
                    if(scope===district&&!signal.aborted)
                        loading(source.name+' · '+key+'…',loadDone,loadTotal);
                    if(source.transport==='snapshot'){
                        const base='/catastro/api/maestro/vectores/'+encodeURIComponent(current)+'/'+key+'/';
                        const manifest=await snapshotJson(base+'manifiesto/',signal);
                        collection={source,key,district:current,records:[]};
                        collections.set(id,collection);
                        for(let part=1;part<=manifest.parts;part++){
                            if(signal.aborted)return;
                            if(scope===district)
                                loading(source.name+' · '+key+' · parte '+part+'/'+manifest.parts,
                                    loadDone+(part-1)/Math.max(1,manifest.parts),loadTotal);
                            const data=await snapshotJson(base+'?part='+part,signal);
                            const records=(data.features||[]).map(f=>record(f,source,key)).filter(Boolean);
                            collection.records.push(...records);
                            if(vectorLayer&&records.length)
                                await addVectorFeatures({source,key,district:current,records});
                            counts();
                        }
                    }else{
                        let result;
                        if(client)result=await client.load({ubigeo:current,layers:source.layers,service_base:source.service_base},key,{signal,onBatch:(_,snapshot)=>{
                            if(scope===district&&!signal.aborted)status('Cargando '+source.name+' · '+key+': '+fmt(snapshot.processed)+' de '+fmt(snapshot.total_in_view));
                        }});
                        else result=await json('/catastro/api/maestro/fuentes/'+encodeURIComponent(source.id)+'/'+key+'/?ubigeo='+current,signal);
                        if(signal.aborted)return;
                        collection={source,key,district:current,records:result.features.map(f=>record(f,source,key)).filter(Boolean)};
                        collections.set(id,collection);
                        if(vectorLayer)await addVectorFeatures(collection);
                    }
                    if(signal.aborted||!collection)return;
                    if(scope===district&&!signal.aborted){
                        loadDone++;
                        loading(source.name+' · '+key+': '+fmt(collection.records.length)+' elementos',loadDone,loadTotal);
                    }
                })().finally(()=>pending.delete(id));pending.set(id,task);
            }
            await task;if(signal.aborted||district!==scope)return;
            counts();
        }
    }
    async function refresh(fitAfter=false) {
        controller?.abort();controller=new AbortController();const signal=controller.signal;
        if(selectedFeature)vectorLayer?.revertStyle(selectedFeature);
        selected=null;selectedFeature=null;vectorLayer?.setStyle(vectorStyle);counts();
        const sources=catalog.sources.filter(s=>s.active&&masterRole(s)&&
            (district===ALL_DISTRICTS||s.districts.includes(district))&&enabled.get(s.id));
        const layerNames=['manzanas','lotes','vias'];
        loadTotal=sources.reduce((sum,s)=>sum+layerNames.filter(key=>Number(s.layers?.[key]?.count||0)).length,0);
        loadDone=0;
        status(sources.length?'Cargando los registros del Catastro Maestro…':'Este distrito todavía no tiene registros activos en el Catastro Maestro.');
        loading(sources.length?'Cargando el Catastro Maestro…':'',0,loadTotal||1);
        try{
            let next=0,finished=0;
            async function worker(){
                while(next<sources.length&&!signal.aborted){
                    const source=sources[next++];
                    await loadSource(source,signal);
                    finished++;
                    if(district===ALL_DISTRICTS&&!signal.aborted)
                        status('Catastro Maestro · '+finished+' de '+sources.length+' distritos cargados…');
                }
            }
            const concurrency=district===ALL_DISTRICTS?2:4;
            await Promise.all(Array.from({length:Math.min(concurrency,sources.length)},()=>worker()));
            if(signal.aborted)return;
            loading(null);
            counts();if(fitAfter)fit();
            if(sources.length)status((map?'Catastro Maestro cargado · ':'Catastro Maestro cargado sin Google Maps · ')+districtLabel(district)+' · fuente de verdad D1.');
        }catch(error){if(error.name!=='AbortError'&&!signal.aborted)status(error.message,true);}
    }
    function showCaymaReference(updateUrl=true) {
        if(!catalog||!el('district'))return;
        enabled.set('cayma-pud-2006-eu03',true);
        el('district').value='040103';
        if(updateUrl){
            const url=new URL(location.href);
            url.searchParams.set('ubigeo','040103');
            url.searchParams.set('cayma','1');
            history.replaceState(null,'',url);
        }
        changeDistrict(true);
        status('Cayma · plano municipal de 2006 · referencia temporal sin validar.');
    }
    function sourcesPanel() {
        el('sources').replaceChildren();
        const sources=catalog.sources.filter(s=>s.active&&masterRole(s)&&
            (district===ALL_DISTRICTS||s.districts.includes(district)));
        if(!sources.length){const p=document.createElement('p');p.className='master-help';p.textContent='Este distrito todavía no tiene registros activos en el Catastro Maestro.';el('sources').append(p);}
        for(const source of sources){
            enabled.set(source.id,true);
            const card=document.createElement('article'),label=document.createElement('label'),check=document.createElement('input'),name=document.createElement('span');
            card.className='master-source';label.className='master-check';check.type='checkbox';check.checked=enabled.get(source.id);name.textContent=source.name;label.append(check,name);card.append(label);
            check.addEventListener('change',()=>{enabled.set(source.id,check.checked);refresh(false);});
            const badge=document.createElement('span');badge.className='master-badge';badge.textContent=source.role==='snapshot'?'Vectores extraídos · ficha pendiente':'Maestro · registro normalizado';card.append(badge);
            const p=document.createElement('p');p.className='master-help';p.textContent='Capas disponibles: '+fmt(source.layers.lotes?.count||0)+' lotes y '+fmt(source.layers.manzanas?.count||0)+' manzanas. Cada capa se conserva de forma independiente.';card.append(p);
            el('sources').append(card);
        }
        counts();
    }
    function changeDistrict(fitAfter=true) {
        const requested=el('district').value;
        if(parkDirty()){
            el('district').value=district;
            parkStatus('Guarda o cancela los cambios de parques antes de cambiar de distrito.',true);
            return;
        }
        district=requested;selected=null;closeDetailCard(false);
        const url=new URL(location.href);url.searchParams.set('ubigeo',district);history.replaceState(null,'',url);sourcesPanel();loadParkLots();refresh(fitAfter);
        window.dispatchEvent(new CustomEvent('catastro-master-district',{detail:{ubigeo:district}}));
    }
    function showCatalogueError(error) {
        const panel=el('sources');panel.replaceChildren();
        const message=document.createElement('p');message.className='master-help';message.dataset.error='true';
        message.textContent=error?.message||'No se pudieron consultar las fuentes del Catastro Maestro.';
        const retry=document.createElement('button');retry.type='button';retry.textContent='Reintentar fuentes';
        retry.addEventListener('click',()=>{cataloguePromise=null;prepareCatalogue();});
        panel.append(message,retry);status(message.textContent,true);
    }
    function prepareCatalogue() {
        if(cataloguePromise)return cataloguePromise;
        cataloguePromise=(async()=>{
            status('Cargando distritos y fuentes del Catastro Maestro…');
            catalog=await json('/catastro/api/maestro/catalogo/');
            const districtSelect=el('district');districtSelect.replaceChildren();
            const masterDistricts=new Set(catalog.sources.filter(s=>s.active&&masterRole(s)).flatMap(s=>s.districts));
            if(masterDistricts.size){const option=document.createElement('option');option.value=ALL_DISTRICTS;option.textContent='Todos los distritos D1 · '+masterDistricts.size+' con registros';districtSelect.append(option);}
            for(const d of catalog.districts){const option=document.createElement('option');option.value=d.ubigeo;option.textContent=d.name+(masterDistricts.has(d.ubigeo)?'':' · sin registros maestros');districtSelect.append(option);}
            const requested=new URL(location.href).searchParams.get('ubigeo');
            const fallback=catalog.districts.find(d=>masterDistricts.has(d.ubigeo));
            districtSelect.value=requested===ALL_DISTRICTS&&masterDistricts.size?ALL_DISTRICTS:
                (masterDistricts.has(requested)?requested:(fallback?.ubigeo||catalog.districts[0]?.ubigeo||''));
            districtSelect.disabled=false;
            if(!districtSelect.dataset.ready){districtSelect.addEventListener('change',()=>changeDistrict(true));districtSelect.dataset.ready='true';}
            if(caymaRequested())enabled.set('cayma-pud-2006-eu03',true);
            changeDistrict(false);
            return catalog;
        })().catch(error=>{cataloguePromise=null;showCatalogueError(error);throw error;});
        return cataloguePromise;
    }
    window.initCatastroMaster=async()=>{
        if(map)return fit();
        map=new google.maps.Map(el('map'),{center:{lat:-16.36,lng:-71.545},zoom:14,mapTypeControl:false,streetViewControl:false,fullscreenControl:true,clickableIcons:false});
        makeVectorLayer();
        for(const collection of collections.values())addVectorFeatures(collection);
        window.CatastroMasterMap={getMap:()=>map};
        window.dispatchEvent(new CustomEvent('catastro-master-ready',{detail:{map}}));
        el('detail-close')?.addEventListener('click',()=>closeDetailCard(true));
        document.addEventListener('keydown',event=>{
            if(event.key==='Escape'&&el('detail-card')&&!el('detail-card').hidden)closeDetailCard(true);
        });
        map.addListener('click',event=>{
            const point=[event.latLng.lng(),event.latLng.lat()];
            if(parkMode)toggleParkAt(point);else selectAt(point);
        });
        el('park-search')?.addEventListener('click',()=>{
            if(!district||district===ALL_DISTRICTS){parkStatus('Selecciona un distrito concreto para editar parques.',true);return;}
            parkMode=!parkMode;parkControls();
            parkStatus(parkMode?'Modo búsqueda activo: un clic marca el lote; otro clic lo desmarca.':'Modo búsqueda cerrado. Puedes guardar o cancelar los cambios.');
        });
        el('park-save')?.addEventListener('click',async()=>{
            if(!district||district===ALL_DISTRICTS||!parkDirty())return;
            const button=el('park-save');button.disabled=true;
            parkStatus('Guardando '+parkDraft.size+' lotes como parques…');
            try{
                const response=await fetch('/catastro/api/maestro/parques/',{
                    method:'POST',credentials:'same-origin',cache:'no-store',
                    headers:{Accept:'application/json','Content-Type':'application/json',
                        'X-CSRFToken':el('raster-upload')?.elements?.csrfmiddlewaretoken?.value||''},
                    body:JSON.stringify({ubigeo:district,lots:[...parkDraft],token:parkToken})
                });
                const value=await response.json();
                if(!response.ok)throw Error(value.error||'No se pudieron guardar los parques.');
                parkToken=value.token;parkSaved=new Set(value.lots||[]);parkDraft=new Set(parkSaved);
                parkMode=false;refreshParkStyles();parkControls();
                parkStatus('Cambios guardados · '+parkSaved.size+' lotes marcados como parque.');
            }catch(error){parkStatus(error.message,true);parkControls();}
        });
        el('park-cancel')?.addEventListener('click',()=>{
            parkDraft=new Set(parkSaved);parkMode=false;refreshParkStyles();parkControls();
            parkStatus('Cambios descartados · '+parkSaved.size+' lotes marcados como parque.');
        });
        el('fit').addEventListener('click',fit);
        el('satellite').addEventListener('click',()=>{const value=map.getMapTypeId()!=='satellite';map.setMapTypeId(value?'satellite':'roadmap');el('satellite').setAttribute('aria-pressed',String(value));});
        for(const key of ['manzanas','lotes','vias'])el(key).addEventListener('change',()=>{
            layerOn[key]=el(key).checked;
            if(selectedFeature){vectorLayer.revertStyle(selectedFeature);selected=null;selectedFeature=null;}
            counts();vectorLayer.setStyle(vectorStyle);
        });
        try{
            await prepareCatalogue();fit();
        }catch(_){/* The catalogue already renders its own retry state. */}
    };
    const startCatalogue=()=>prepareCatalogue().catch(()=>{});
    el('cayma-preview')?.addEventListener('click',()=>{
        if(catalog)showCaymaReference(true);
        else prepareCatalogue().then(()=>showCaymaReference(true)).catch(()=>{});
    });
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',startCatalogue,{once:true});
    else startCatalogue();
})();
