/* Source versions are immutable; only reviewed selections change the draft. */
(() => {
    'use strict';
    const endpoint='/catastro/api/maestro/composicion/';
    const $=id=>document.getElementById('sources-'+id);
    function paths(collection){
        const items=(collection.features||[]).filter(f=>['Polygon','MultiPolygon'].includes(f.geometry?.type));
        const rings=f=>(f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates).flat();
        const points=items.flatMap(f=>rings(f).flat());
        if(!points.length)return [];
        const lat=points.reduce((sum,p)=>sum+p[1],0)/points.length,cos=Math.cos(lat*Math.PI/180);
        let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
        for(const p of points){const x=p[0]*cos,y=-p[1];minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
        const scale=Math.min(900/(maxX-minX||1),260/(maxY-minY||1));
        return items.map(f=>({id:f.id,d:rings(f).map(ring=>ring.map((p,i)=>(i?'L':'M')+
            ((p[0]*cos-minX)*scale+20).toFixed(2)+','+((-p[1]-minY)*scale+20).toFixed(2)).join(' ')+' Z').join(' ')}));
    }
    if(typeof module!=='undefined')module.exports={paths};
    if(typeof document==='undefined'||!$('workspace'))return;
    let state=null,comparison=null,busy=false,comparisonSerial=0;
    const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=String(text);if(cls)e.className=cls;return e;};
    function status(text,error=false){$('status').textContent=text;$('status').dataset.error=String(error);}
    function invalidate(){comparison=null;comparisonSerial++;$('apply').disabled=true;}
    function csrf(){return document.querySelector('#sources-pdf-form [name=csrfmiddlewaretoken]').value;}
    async function api(payload=null,query=''){
        const response=await fetch(endpoint+query,{credentials:'same-origin',cache:'no-store',
            method:payload?'POST':'GET',headers:{Accept:'application/json',...(payload?{'Content-Type':'application/json','X-CSRFToken':csrf()}:{} )},
            ...(payload?{body:JSON.stringify(payload)}:{})});
        if(!response.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para administrar las fuentes.');
        const value=await response.json();if(!response.ok)throw Error(value.error||'No se pudo completar la solicitud.');return value;
    }
    function setBusy(value){busy=value;document.querySelectorAll('#sources-workspace button:not([data-calibration-button])').forEach(b=>{b.disabled=value;});$('apply').disabled=value||!comparison;}
    async function mutate(task){
        if(busy)return;setBusy(true);
        try{await task();}catch(error){invalidate();status(error.message,true);}finally{setBusy(false);}
    }
    function render(){
        $('stats').replaceChildren();
        for(const p of state.projects){const card=node('div',null,'sources-stat');card.append(node('strong',p.registered_sheets+' / '+p.expected_sheets),node('span','Láminas registradas · '+p.name));$('stats').append(card);}
        for(const [value,label] of [[state.active_entities,'Geometrías activas en este borrador'],[state.revision,'Revisión del borrador']]){
            const card=node('div',null,'sources-stat');card.append(node('strong',value),node('span',label));$('stats').append(card);
        }
        const catalogCounts=state.catalog_counts||{};
        $('catalog-counts').textContent='Catálogo incremental · '+[
            ['Identificadores',catalogCounts.external_identifiers],
            ['Direcciones',catalogCounts.addresses],
            ['Observaciones',catalogCounts.property_observations],
            ['Anuncios',catalogCounts.listings],
            ['Operaciones',catalogCounts.transactions],
            ['Actividades',catalogCounts.activities],
            ['Visitas',catalogCounts.visits],
            ['Proyectos',catalogCounts.developments],
            ['Cobertura',catalogCounts.coverage_records],
        ].map(([label,value])=>label+': '+(value||0)).join(' · ');
        const selected=$('version').value,withdraw=$('withdraw-source').value;
        $('list').replaceChildren();$('version').replaceChildren(node('option','Selecciona una versión'));$('version').firstChild.value='';
        $('withdraw-source').replaceChildren(node('option','Selecciona una fuente'));$('withdraw-source').firstChild.value='';
        for(const source of state.sources){
            const article=node('article',null,'sources-source');article.append(node('h3',source.name),node('small',source.id));
            article.append(node('div',source.role==='backup'?'Respaldo conservado':source.role==='contributing'?'Tiene aportes aplicados':'Candidata · todavía en revisión','sources-tag'));
            for(const version of source.versions){
                article.append(node('p',version.label+' · '+(source.role==='backup'?'Respaldo conservado en el mapa':version.vector_review?(version.vector_review.extractor==='prometeo-pdf-vector-v1'?version.vector_review.vector_paths+' trazos y '+version.vector_review.text_words+' palabras extraídas · coordenadas locales':version.vector_review.candidate_faces+' contornos propuestos · pendientes de revisión'):version.elements+' elementos preparados · '+(version.georeferencing.status==='verified'?'Posición declarada verificada':'Posición pendiente'))));
                if(version.vector_review){const filename=Object.keys(version.vector_artifacts||{}).find(name=>name.endsWith('.html'))||Object.keys(version.vector_artifacts||{}).find(name=>name.endsWith('.geojson'));if(filename){const link=node('a',filename.endsWith('.html')?'Ver capas vectoriales':'Descargar trazos GeoJSON');link.href='/catastro/api/maestro/pdf/'+encodeURIComponent(version.id)+'/vectores/'+encodeURIComponent(filename);if(filename.endsWith('.html')){link.target='_blank';link.rel='noopener';}else link.download=filename;article.append(link);}}
                if(version.original_name)article.append(node('small',version.original_name));
                if(version.original_available){const button=node('button','Ver plano original','secondary');button.type='button';button.addEventListener('click',()=>{
                    const image=node('img');image.alt=source.name+' · '+version.label;image.src='/catastro/api/maestro/pdf/'+encodeURIComponent(version.id)+'/pagina/';image.style.cssText='width:100%;height:auto;background:white;border-radius:8px';
                    $('inspection').replaceChildren(node('h3',source.name),node('p','Plano original · posición y capas todavía por revisar'),image);
                });const link=node('a','Abrir PDF');link.href='/catastro/api/maestro/pdf/'+encodeURIComponent(version.id)+'/original/';link.target='_blank';link.rel='noopener';article.append(button,node('span',' · '),link);}
                const option=node('option',source.name+' / '+version.label);option.value=version.id;$('version').append(option);
            }
            $('list').append(article);
            const option=node('option',source.name);option.value=source.id;$('withdraw-source').append(option);
        }
        if([...$('version').options].some(o=>o.value===selected))$('version').value=selected;
        if([...$('withdraw-source').options].some(o=>o.value===withdraw))$('withdraw-source').value=withdraw;
        const project=$('project').value;$('project').replaceChildren();
        if(!state.projects.length){const o=node('option','Sin proyecto asociado');o.value='';$('project').append(o);}
        for(const p of state.projects){const o=node('option',p.name);o.value=p.id;$('project').append(o);}
        if([...$('project').options].some(o=>o.value===project))$('project').value=project;
        if(!$('fields').children.length){
            const fields=[{key:'$geometry',label:'Geometría / contorno'},...state.fields];
            for(const field of fields){const label=node('label'),input=node('input');input.type='checkbox';input.value=field.key;label.append(input,node('span',field.label));$('fields').append(label);}
            for(const category of state.business_categories){const o=node('option',category.label);o.value=category.code;$('business').append(o);}
        }
        $('history').replaceChildren();
        const table=node('table'),head=node('tr');['Revisión','Cambio','Fecha','Autor','Motivo','Acción'].forEach(s=>head.append(node('th',s)));table.append(head);
        const operationLabels={project:'Registrar proyecto',stage:'Registrar versión',fill:'Completar campos',replace_fields:'Sustituir campos',replace_scope:'Sustituir capa en el ámbito',withdraw_source:'Retirar aporte',restore:'Recuperar selección'};
        const limaDate=new Intl.DateTimeFormat('es-PE',{dateStyle:'short',timeStyle:'medium',timeZone:'America/Lima'});
        for(const entry of state.history){
            const row=node('tr');[entry.revision,operationLabels[entry.operation]||entry.operation,limaDate.format(new Date(entry.created_at)),entry.actor,entry.reason].forEach(v=>row.append(node('td',v)));
            const cell=node('td'),button=node('button','Recuperar','secondary');button.type='button';button.addEventListener('click',()=>mutate(async()=>{
                const reason=$('restore-reason').value.trim();if(!reason)throw Error('Indica el motivo de la reversión.');
                await api({action:'restore',target_revision:entry.revision,revision:state.revision,reason});
                invalidate();await refresh();await queryRecords();status('Selección recuperada. Se conservan versiones, identidades y relaciones.');
            }));cell.append(button);row.append(cell);table.append(row);
        }
        $('history').append(table);modeChanged();
    }
    async function refresh(){state=await api(null,'?'+new URLSearchParams({ubigeo:$('workspace-ubigeo').value.trim()}));render();document.dispatchEvent(new CustomEvent('master-sources-updated',{detail:state}));}
    document.addEventListener('master-sources-refresh',()=>mutate(async()=>{invalidate();await refresh();await queryRecords();}));
    function modeChanged(){
        const withdrawing=$('mode').value==='withdraw_source';$('version').disabled=withdrawing;$('withdraw-source').disabled=!withdrawing;
    }
    function plan(){
        const value={revision:state.revision,mode:$('mode').value,reason:$('reason').value.trim(),
            scope:{ubigeo:$('ubigeo').value.trim(),kind:$('kind').value},fields:[...$('fields').querySelectorAll('input:checked')].map(e=>e.value),identity_map:{}};
        if($('sector').value.trim())value.scope.sector=$('sector').value.trim();
        if($('entities').value.trim())value.scope.entity_ids=$('entities').value.trim().split(/\s+/);
        if(value.mode==='withdraw_source')value.source_id=$('withdraw-source').value;else value.version_id=$('version').value;
        for(const row of $('mapping').children){const inputs=row.querySelectorAll('input');const from=inputs[0].value.trim(),to=inputs[1].value.trim();
            if(from||to){if(!from||!to)throw Error('Completa ambos identificadores de la correspondencia.');if(value.identity_map[from])throw Error('Hay correspondencias de origen repetidas.');value.identity_map[from]=to;}}
        return value;
    }
    function showComparison(value){
        const box=$('comparison');box.replaceChildren(node('p',value.affected_entities+' inmuebles afectados · '+value.changed_fields+' campos · '+value.geometry_changes+' geometrías · '+value.new_entities+' identidades nuevas','sources-result'));
        if(value.without_geometry.length)box.append(node('p',value.without_geometry.length+' inmuebles quedarán sin geometría activa. Se conservan sus identidades y relaciones.'));
        if(value.preserved_existing_fields)box.append(node('p',value.preserved_existing_fields+' campos existentes conservados al completar sólo vacíos.'));
        const wrap=node('div',null,'sources-table-wrap'),table=node('table'),head=node('tr');['Inmueble','Campo','Antes','Después'].forEach(v=>head.append(node('th',v)));table.append(head);
        const format=value=>value==null?'Sin aporte':String(value.value)+' · '+value.version_id;
        const labels=new Map(state.fields.map(f=>[f.key,f.label]));labels.set('$geometry','Geometría');
        for(const detail of value.details){const row=node('tr');[detail.entity_id,labels.get(detail.field)||detail.field,format(detail.before),format(detail.after)].forEach(v=>row.append(node('td',v)));table.append(row);}
        wrap.append(table);box.append(wrap);if(value.details_truncated)box.append(node('p','Se muestran los primeros 150 cambios; los conteos incluyen el ámbito completo.'));
    }
    async function queryRecords(){
        const filters=new URLSearchParams({view:'records'});for(const [key,value] of new FormData($('query')))if(String(value).trim())filters.set(key,String(value).trim());
        const data=await api(null,'?'+filters);const wrap=$('records');wrap.replaceChildren();
        if(!data.records.length){wrap.append(node('p','Todavía no hay inmuebles que coincidan con estos filtros. Registrar un PDF no activa sus datos.'));}
        else{
            const columns=[['entity_id','Identificador maestro'],['kind','Tipo'],['ubigeo','UBIGEO'],['postal_code','Código postal'],['urbanization','Urbanización'],['sector','Sector'],['block','Manzana'],['lot','Lote'],['cuc','CUC'],['land_area','Terreno m²'],['built_area','Construida m²'],['bathrooms','Baños'],['parking_spaces','Cocheras'],['business_category','Actividad'],['registry_entry_number','Partida'],['has_geometry','Contorno activo']];
            const table=node('table'),head=node('tr');columns.forEach(c=>head.append(node('th',c[1])));head.append(node('th','Ficha y documentos'));table.append(head);
            for(const record of data.records){const row=node('tr');columns.forEach(c=>row.append(node('td',record[c[0]]??'Sin dato')));const cell=node('td'),button=node('button','Abrir ficha','secondary');button.type='button';button.addEventListener('click',()=>mutate(()=>showEntity(record.entity_id)));cell.append(button);row.append(cell);table.append(row);}wrap.append(table);
            if(data.records.length===1000)wrap.append(node('p','Se muestran hasta 1.000 registros; afina los filtros para consultar otros.'));
        }
        const district=$('query').elements.ubigeo.value.trim();
        if(/^[0-9]{6}$/.test(district)){
            const data=await api(null,'?'+new URLSearchParams({view:'geometry',ubigeo:district,kind:'lote'}));
            $('geometry').replaceChildren();const contours=paths(data);
            if(contours.length){
                const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 940 300');svg.setAttribute('role','img');svg.setAttribute('aria-label','Contornos de lotes activos en el borrador');
                for(const contour of contours){const path=document.createElementNS(ns,'path');path.setAttribute('d',contour.d);path.setAttribute('stroke','#6ce2bd');path.setAttribute('fill','#2e8d7130');path.setAttribute('stroke-width','.8');path.setAttribute('fill-rule','evenodd');const title=document.createElementNS(ns,'title');title.textContent=contour.id;path.append(title);svg.append(path);}
                $('geometry').append(node('p','Contornos activos del borrador · sin mapa base'),svg);
            }
        }
    }
    async function showEntity(id){
        const data=await api(null,'?'+new URLSearchParams({view:'entity',id}));
        let box=document.getElementById('sources-record-detail');
        if(!box){box=node('div');box.id='sources-record-detail';$('records').parentElement.append(box);}
        box.replaceChildren(node('h3','Ficha · '+data.entity.id));
        const labels=new Map(state.fields.map(f=>[f.key,f.label]));
        const table=node('table');
        for(const [key,value] of Object.entries(data.attributes)){
            if(value==null||key==='entity_id')continue;
            const row=node('tr');row.append(node('th',labels.get(key)||key),node('td',value),node('td',data.provenance[key]?.version_id||'Identidad territorial'));table.append(row);
        }
        box.append(table,node('h4','Titulares según documentos'));
        if(!data.owners.length)box.append(node('p','Sin titulares documentados vinculados a esta entidad.'));
        for(const person of data.owners)box.append(node('p',person.name+' · '+(person.document_type||'Documento no alineado')+' '+(person.document_number||'')+' · '+person.source_version));
        box.append(node('h4','PDF y fotografías'));
        if(!data.media.length)box.append(node('p','Sin archivos vinculados a esta entidad.'));
        for(const item of data.media){const link=node('a',(item.kind||'Archivo')+' · '+item.source_version);link.href=item.url;link.target='_blank';link.rel='noopener';const p=node('p');p.append(link);box.append(p);}
        if(data.boundary_segments?.length){
            const sides={front:'Frente',back:'Fondo',left:'Izquierda',right:'Derecha',other:'Otro lindero',unknown:'Lado pendiente de clasificar'};
            box.append(node('h4','Segmentos del perímetro'));
            for(const side of data.boundary_segments)box.append(node('p',(sides[side.side]||side.side)+' · '+(side.length_m==null?'Sin longitud documental':side.length_m+' m')+' · '+side.source_version));
        }
        if(data.registral_acts?.length){box.append(node('h4','Antecedentes registrales documentados'));
            for(const act of data.registral_acts)box.append(node('p',act.kind+' · '+(act.registry_number||'Sin partida consignada')+' · '+(act.observed_at||'Sin fecha consignada')+' · '+act.source_version));}
        const catalog=data.catalog||{};
        if(catalog.addresses?.length){box.append(node('h4','Direcciones documentadas'));
            for(const item of catalog.addresses)box.append(node('p',(item.address_type||'Dirección')+' · '+(item.full_address||[item.street_type,item.street_name,item.municipal_number].filter(Boolean).join(' ')||'Sin texto de dirección')+' · '+(item.precision||'Precisión sin dato')+' · '+item.status+' · '+item.source_version));}
        if(catalog.identifiers?.length){box.append(node('h4','Identificadores externos'));
            for(const item of catalog.identifiers)box.append(node('p',item.scheme+' · '+item.value+' · '+item.status+' · '+(item.observed_at||'Sin fecha')+' · '+item.source_version));}
        if(catalog.observations?.length){box.append(node('h4','Atributos y observaciones adicionales'));
            for(const item of catalog.observations)box.append(node('p',(item.namespace||'general')+' / '+item.field_name+' · '+String(item.value)+(item.unit?' '+item.unit:'')+' · '+item.status+' · '+item.source_version));}
        if(catalog.listings?.length){box.append(node('h4','Publicaciones de mercado'));
            for(const item of catalog.listings){
                const p=node('p',item.portal+' · '+item.external_id+' · '+(item.operation||'Operación sin dato')+' · '+(item.price==null?'Precio sin dato':item.price+' '+(item.currency||''))+' · '+item.status+' · '+(item.last_seen||'Sin fecha'));
                if(item.url){const link=node('a',' Abrir anuncio');link.href=item.url;link.target='_blank';link.rel='noopener';p.append(link);}box.append(p);
            }
            for(const item of catalog.listing_history||[])box.append(node('p','Historial · '+(item.observed_at||'Sin fecha')+' · '+(item.price==null?'Precio sin dato':item.price+' '+(item.currency||''))+' · '+item.status));
        }
        if(catalog.transactions?.length){box.append(node('h4','Operaciones documentadas'));
            for(const item of catalog.transactions)box.append(node('p',item.transaction_type+' · '+(item.amount==null?'Monto sin dato':item.amount+' '+(item.currency||''))+' · '+(item.transaction_date||'Fecha sin dato')+' · '+item.source_version));}
        if(catalog.activities?.length){box.append(node('h4','Actividades y establecimientos'));
            for(const item of catalog.activities)box.append(node('p',(item.activity_name||item.category||'Actividad sin nombre')+' · '+(item.category||'Sin categoría')+' · '+(item.ciiu_code?('CIIU '+(item.ciiu_version||'')+' '+item.ciiu_code):'CIIU sin dato')+' · '+(item.organization_name||'Organización sin dato')+' · '+item.source_version));}
        if(catalog.visits?.length){box.append(node('h4','Visitas y observaciones'));
            for(const item of catalog.visits)box.append(node('p',(item.visited_at||'Sin fecha')+' · '+(item.summary||'Sin resumen')+' · '+(item.observer||'Observador no consignado')+' · '+item.source_version));}
        if(catalog.development_links?.length){box.append(node('h4','Proyectos inmobiliarios relacionados'));
            for(const item of catalog.development_links)box.append(node('p',item.name+' · '+item.status+' · '+(item.role||'Relación sin clasificar')+' · '+item.source_version));}
        for(const relation of data.relationships){const button=node('button','Abrir inmueble relacionado · '+relation.kind,'secondary');button.type='button';button.addEventListener('click',()=>mutate(()=>showEntity(relation.related_entity_id)));box.append(button);}
    }
    async function queryCatalog(){
        const params=new URLSearchParams({view:'catalog'});
        for(const [key,value] of new FormData($('catalog-query')))if(String(value).trim())params.set(key,String(value).trim());
        const data=await api(null,'?'+params);const wrap=$('catalog-results');wrap.replaceChildren();
        $('catalog-status').textContent=data.items.length+' registros candidatos. No se activó ningún dato.';
        if(!data.items.length){wrap.append(node('p','No hay registros de catálogo para estos filtros.'));return;}
        const table=node('table'),head=node('tr');
        ['Tipo','Etiqueta','Detalle','Entidad','Fecha','Valor','Estado','Fuente','Acción'].forEach(label=>head.append(node('th',label)));table.append(head);
        const labels={listing:'Anuncio',identifier:'Identificador',observation:'Observación',transaction:'Operación',activity:'Actividad',coverage:'Cobertura'};
        for(const item of data.items){
            const row=node('tr');[labels[item.kind]||item.kind,item.label||'',item.detail||'',item.entity_id||'Sin vínculo',item.observed_at||'Sin fecha',
                item.amount==null?'':String(item.amount)+(item.currency?' '+item.currency:''),item.status||'',item.source_version||'']
                .forEach(value=>row.append(node('td',value)));
            const cell=node('td');
            if(item.entity_id){const button=node('button','Abrir ficha','secondary');button.type='button';button.addEventListener('click',()=>mutate(()=>showEntity(item.entity_id)));cell.append(button);}
            row.append(cell);table.append(row);
        }
        wrap.append(table);
        if(data.items.length===1000)wrap.append(node('p','Se muestran hasta 1.000 registros; afina los filtros.'));
    }
    $('change-form').addEventListener('input',invalidate);$('change-form').addEventListener('change',()=>{invalidate();modeChanged();});
    $('add-mapping').addEventListener('click',()=>{const row=node('div',null,'sources-mapping-row'),from=node('input'),to=node('input'),remove=node('button','Quitar','secondary');from.placeholder='Origen: lote:identificador-en-la-fuente';to.placeholder='Identificador del inmueble maestro';from.setAttribute('aria-label','Tipo e identificador de origen');to.setAttribute('aria-label','Identificador maestro');remove.type='button';remove.addEventListener('click',()=>{row.remove();invalidate();});row.append(from,to,remove);$('mapping').append(row);invalidate();});
    $('change-form').addEventListener('submit',event=>{event.preventDefault();mutate(async()=>{
        invalidate();const serial=comparisonSerial,p=plan(),signature=JSON.stringify(p);const value=await api({action:'preview',plan:p});
        if(serial!==comparisonSerial||JSON.stringify(plan())!==signature){status('Los campos cambiaron durante la comparación. Compara otra vez.');return;}
        comparison={plan:p,token:value.token};showComparison(value);status('Comparación preparada. Revisa el ámbito y los cambios.');
    });});
    $('apply').addEventListener('click',()=>mutate(async()=>{if(!comparison)return;if(JSON.stringify(plan())!==JSON.stringify(comparison.plan))throw Error('Compara otra vez después de cambiar el formulario.');
        const value=await api({action:'apply',...comparison});invalidate();await refresh();await queryRecords();status(value.unchanged?'El aporte no cambia los valores actuales.':state.storage==='d1'?'Cambio confirmado en D1.':'Cambio aplicado únicamente al borrador local.');
    }));
    $('query').addEventListener('submit',event=>{event.preventDefault();mutate(queryRecords);});
    $('catalog-query').addEventListener('submit',event=>{event.preventDefault();mutate(queryCatalog);});
    $('scope-form').addEventListener('submit',event=>{event.preventDefault();mutate(async()=>{
        const district=$('workspace-ubigeo').value.trim();$('ubigeo').value=district;$('query').elements.ubigeo.value=district;
        $('pdf-form').elements.ubigeo.value=district;invalidate();await refresh();await queryRecords();status('Distrito abierto. Se conservan los datos de los otros ámbitos.');
    });});
    $('pdf-form').addEventListener('submit',event=>{event.preventDefault();mutate(async()=>{
        const form=$('pdf-form'),data=new FormData(form),metadata=Object.fromEntries([...data.entries()].filter(([key])=>!['document','csrfmiddlewaretoken'].includes(key)));
        metadata.revision=state.revision;metadata.version_id=metadata.source_id+':'+Date.now();data.set('metadata',JSON.stringify(metadata));
        const response=await fetch('/catastro/api/maestro/pdf/',{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','X-CSRFToken':csrf()},body:data});
        if(!response.headers.get('content-type')?.includes('application/json'))throw Error('No se pudo registrar el PDF. Revisa la sesión o el tamaño del archivo.');
        const value=await response.json();if(!response.ok)throw Error(value.error||'No se pudo registrar el PDF.');invalidate();await refresh();
        $('inspection').replaceChildren(node('p',value.inspection.pages+' páginas · '+value.inspection.layers.length+' capas originales'),node('p',value.inspection.layers.join(' · ')));status(value.notice);
    });});
    $('import').addEventListener('click',()=>mutate(async()=>{
        const file=$('normalized').files[0];if(!file||file.size>12*1024*1024)throw Error('Selecciona un aporte JSON de hasta 12 MB.');
        const payload=JSON.parse(await file.text());await api({action:'stage',revision:state.revision,payload});invalidate();await refresh();status('Versión candidata registrada. Sus datos todavía no están activos.');
    }));
    mutate(async()=>{await refresh();await queryRecords();status('Borrador listo. La extracción de COFOPRI permanece detenida.');});
})();
