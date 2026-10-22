(() => {
  'use strict';
  const PIPELINE=Object.freeze([
    {id:'registered',label:'Registro e integridad',detail:'Fuente, distrito, versión y original inmutable.',description:'Se registran la procedencia, la fecha y el SHA-256. El archivo queda conservado, pero todavía no aporta geometrías ni atributos.',result:'Original recuperable y versión candidata.',gate:'Abrir e inspeccionar el contenido del archivo.'},
    {id:'extract',label:'Inspección y extracción',detail:'Inventario técnico y elementos candidatos.',description:'Se revisan páginas o capas y se extraen trazos, textos, cotas, registros o entidades. Un PDF vectorial produce coordenadas locales; un DWG se convierte e inventaría.',result:'Elementos candidatos con procedencia.',gate:'Clasificar lotes, manzanas, calles, registros y vínculos.'},
    {id:'review',label:'Revisión de elementos',detail:'Topología, rótulos y significado revisados.',description:'Se comprueba qué representa cada trazo o registro, se cierran contornos, se revisan huecos, solapes, números de lote, calles y cotas.',result:'Capa candidata depurada; aún no homologada.',gate:'Declarar CRS y controles de posición con evidencia.'},
    {id:'georef',label:'Georreferenciación',detail:'Posición declarada y revisable.',description:'Se relacionan puntos del archivo con coordenadas de control y se calculan errores. La propuesta permanece pendiente hasta que la posición y sus controles sean revisados.',result:'Geometría con posición revisable.',gate:'Relacionar cada elemento con una identidad del maestro.'},
    {id:'homologation',label:'Homologación y comparación',detail:'Identidades y cambios comparados.',description:'Se enlazan lotes y registros con entidades existentes y se compara qué campos, geometrías o vínculos cambiarían. No se fusionan inmuebles por proximidad o nombre.',result:'Mapa de identidades y comparación reversible.',gate:'Elegir ámbito, campos y motivo; revisar el efecto antes de aplicar.'},
    {id:'activation',label:'Activación y cobertura',detail:'Aporte revisado incorporado al maestro.',description:'Se aplica únicamente el ámbito revisado. La fuente pasa a contribuyente, se actualizan ficha, cobertura e historial, y el cambio puede revertirse sin borrar identidades.',result:'Datos activos, trazables y reversibles.',gate:'Controlar resultados en ficha, visor, ACM y Cuadrantización.'},
  ]);
  const stageDefinition=id=>PIPELINE.find(stage=>stage.id===id)||PIPELINE[0];
  function pipelineStage(file){
    if(file.role==='backup')return 'backup';
    if(file.role==='contributing'&&Number(file.elements||0)>0)return 'activation';
    if(file.georeferencing?.status==='verified')return 'homologation';
    const vector=file.vector_review||{};
    const reviewApproved=['approved','reviewed','verified'].includes(String(vector.status||vector.review_status||''));
    if(reviewApproved)return 'georef';
    if(file.vector_review)return 'review';
    return 'extract';
  }
  function dwgStage(file){
    if(file.status==='completed')return 'review';
    return 'extract';
  }
  if(typeof module!=='undefined')module.exports={PIPELINE,pipelineStage,dwgStage};
  if(typeof document==='undefined')return;
  const root=document.getElementById('plan-hub');if(!root)return;
  const $=id=>document.getElementById(id),status=$('plan-status');let busy=false;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(cls)n.className=cls;return n;};
  function setStatus(text,error=false){status.textContent=text;status.dataset.error=String(error);}
  function render(portfolio,dwgRows,scope){
    let files=(portfolio.files||[]).filter(x=>x.version_id);
    let cad=dwgRows||[];
    if(scope){files=files.filter(x=>x.ubigeo===scope);cad=cad.filter(x=>x.ubigeo===scope);}
    const decorated=files.map(file=>{const stage=pipelineStage(file),definition=stageDefinition(stage);return {...file,kind:'PDF',stageCode:stage,stage:stage==='backup'?'Respaldo':definition.label,detail:stage==='backup'?'Respaldo retenido y excluido de la ruta de activación.':definition.detail};});
    const dwg=cad.map(file=>{const stage=dwgStage(file),definition=stageDefinition(stage);return {...file,kind:'DWG',name:(file.source_name||file.filename)+' · '+(file.sheet_code||'sin lámina'),stageCode:stage,stage:definition.label,detail:file.status==='completed'?`${file.drawable||0} entidades dibujables · ${file.layer_count??file.layers?.length??0} capas · unidades CAD ${file.units??'sin definir'}`:file.message||'Conversión en proceso'};});
    const all=[...decorated,...dwg];
    const workflowFiles=all.filter(x=>x.stageCode!=='backup');
    const counts=Object.fromEntries(PIPELINE.map(stage=>[stage.id,stage.id==='registered'?workflowFiles.length:workflowFiles.filter(item=>item.stageCode===stage.id).length]));
    const activeRows=portfolio.active_by_district||[];const active=activeRows.filter(x=>!scope||x.ubigeo===scope).reduce((n,x)=>n+Number(x.geometries||0),0);
    const projects=(portfolio.projects||[]).filter(x=>!scope||x.ubigeo===scope);
    $('plan-stats').replaceChildren(...[[all.length,'Planos registrados en el ámbito'],[decorated.length,'Versiones PDF'],[counts.extract,'PDF/DWG por extraer o inspeccionar'],[dwg.length,'DWG locales registrados'],[dwg.filter(x=>x.status==='completed').length,'DWG con capas leídas'],[active,'Geometrías activas del maestro'],[projects.reduce((n,p)=>n+Number(p.expected_sheets||0),0),'Láminas previstas en proyectos']].map(([value,label])=>{const card=el('article',null,'plan-stat');card.append(el('strong',value),el('span',label));return card;}));
    const stages=$('plan-stages'),backups=decorated.filter(x=>x.stageCode==='backup').length;
    stages.replaceChildren(...PIPELINE.map((stage,index)=>{const value=counts[stage.id]||0,card=el('article',null,'plan-stage'+(value?' has-work':'')+(index===0?' base':''));card.append(el('span',String(index+1).padStart(2,'0'),'plan-stage-index'),el('small',index===0?`${value} archivos registrados`:`${value} archivos aquí`,'plan-stage-count'),el('b',stage.label),el('p',stage.description,'plan-stage-description'),el('p',stage.result,'plan-stage-output'),el('p',stage.gate,'plan-stage-gate'));return card;}));
    if(backups)stages.append(el('p',`${backups} respaldo${backups===1?'':'s'} conservado${backups===1?'':'s'} fuera de la ruta. No se presentan como aportes activos ni avanzan por estas etapas.`,'plan-stage-backup'));
    const districtMap=new Map();const district=key=>{if(!districtMap.has(key))districtMap.set(key,{ubigeo:key,pdf:0,pending:0,review:0,verified:0,applied:0,dwg:0,active:0});return districtMap.get(key);};
    for(const f of decorated){const d=district(f.ubigeo||'Sin UBIGEO');d.pdf++;if(f.stageCode==='extract')d.pending++;if(f.stageCode==='review')d.review++;if(f.georeferencing?.status==='verified')d.verified++;if(f.stageCode==='activation')d.applied++;}
    for(const f of dwg){district(f.ubigeo||'Sin UBIGEO').dwg++;}
    for(const f of activeRows)if(!scope||f.ubigeo===scope)district(f.ubigeo).active=Number(f.geometries||0);
    const hostDistricts=$('plan-districts');hostDistricts.replaceChildren();
    if(districtMap.size){const table=el('table'),thead=el('thead'),head=el('tr');for(const title of ['UBIGEO','PDF','Por vectorizar','En revisión','Posición verificada','Aportes activos','DWG','Geometrías activas'])head.append(el('th',title));thead.append(head);table.append(thead);const body=el('tbody');for(const d of [...districtMap.values()].sort((a,b)=>a.ubigeo.localeCompare(b.ubigeo))){const row=el('tr');for(const val of [d.ubigeo,d.pdf,d.pending,d.review,d.verified,d.applied,d.dwg,d.active])row.append(el('td',val));body.append(row);}table.append(body);hostDistricts.append(table);}
    for(const project of projects){const p=el('p',`${project.name} · ${project.registered_sheets||0} / ${project.expected_sheets||0} láminas registradas · ${project.ubigeo}`,'plan-project-progress');hostDistricts.append(p);}
    const host=$('plan-inventory');host.replaceChildren();if(!all.length){host.append(el('p','No hay PDF ni DWG registrados para este ámbito. Los archivos que no se han incorporado al gestor no aparecen en este inventario.','plan-empty'));return;}
    for(const item of all){const card=el('article',null,'plan-item');card.append(el('span',item.kind+' · '+item.stage,'plan-pill'),el('h3',item.name||item.filename),el('p',item.detail));
      if(item.kind==='PDF'){card.append(el('p',`UBIGEO ${item.ubigeo||'—'} · ${item.sheet_code||'sin lámina'} · ${item.elements||0} atributos preparados · ${item.georeferencing?.status||'posición pendiente'} · ${item.original_name||'nombre original no registrado'}`));if(item.vector_review)card.append(el('p',`${item.vector_review.vector_paths||0} trazos · ${item.vector_review.text_words||0} palabras · ${item.vector_review.coordinate_space||'coordenadas locales'} · ningún lote identificado automáticamente`));}
      else card.append(el('p',`UBIGEO ${item.ubigeo||'sin asignar'} · ${item.filename||''} · SHA256 ${item.sha256||'pendiente'}`));
      const actions=el('div',null,'plan-item-actions');
      if(item.kind==='PDF'){const manage=el('a','Administrar fuente');manage.href='/catastro/maestro/fuentes/';actions.append(manage);if(item.original_available){const pdf=el('a','Abrir PDF');pdf.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/original/';pdf.target='_blank';pdf.rel='noopener';actions.append(pdf);}if(item.vector_review){const filename=Object.keys(item.vector_artifacts||{}).find(x=>x.endsWith('.geojson'));if(filename){const link=el('a','Descargar GeoJSON');link.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectores/'+encodeURIComponent(filename);link.download=filename;actions.append(link);}}else if(item.original_available&&item.stageCode==='extract'){const button=el('button','Vectorizar PDF');button.type='button';button.addEventListener('click',async()=>{button.disabled=true;setStatus('Extrayendo trazos y texto del PDF…');try{const csrf=$('dwg-form').elements.csrfmiddlewaretoken.value;const response=await fetch('/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectorizar/',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf,Accept:'application/json'}});const value=await response.json();if(!response.ok)throw Error(value.error||'Falló la extracción vectorial.');setStatus(value.notice);await refresh(scope);}catch(error){setStatus(error.message,true);button.disabled=false;}});actions.append(button);}const calibrate=el('a','Calibrar posición');calibrate.href='/catastro/maestro/fuentes/#calibration-workspace';actions.append(calibrate);const homologate=el('a','Comparar / homologar');homologate.href='/catastro/maestro/fuentes/#sources-change-form';actions.append(homologate);}
      else{const link=el('a',item.status==='completed'?'Abrir visor CAD':'Ver estado');link.href=item.status==='completed'?'/catastro/visor-planos/?plano='+encodeURIComponent(item.id):'/catastro/api/planos/'+encodeURIComponent(item.id)+'/';link.target=item.status==='completed'?'_blank':'_self';actions.append(link);}
      card.append(actions);host.append(card);
    }
  }
  async function refresh(scope){if(busy)return;busy=true;setStatus('Consultando el catálogo de todos los distritos y los DWG locales…');try{const [a,b]=await Promise.all([fetch('/catastro/api/maestro/planos/',{credentials:'same-origin',cache:'no-store'}),fetch('/catastro/api/planos/inventario/',{credentials:'same-origin',cache:'no-store'})]);const portfolio=await a.json(),cad=await b.json();if(!a.ok)throw Error(portfolio.error||'No se pudo consultar el maestro.');if(!b.ok)throw Error(cad.error||'No se pudo consultar el inventario CAD.');render(portfolio,cad.dwg,scope);setStatus((portfolio.truncated?'Catálogo limitado a 5000 versiones. ':'')+'Inventario listo. Los archivos y sus propuestas siguen separados de los lotes aprobados.');}catch(error){setStatus(error.message,true);}finally{busy=false;}}
  $('plan-filter').addEventListener('submit',event=>{event.preventDefault();refresh($('plan-filter').elements.ubigeo.value.trim());});$('plan-refresh').addEventListener('click',()=>refresh($('plan-filter').elements.ubigeo.value.trim()));
  $('dwg-form').addEventListener('submit',async event=>{event.preventDefault();if(busy)return;busy=true;const button=event.currentTarget.querySelector('button[type=submit]');button.disabled=true;setStatus('Subiendo DWG e iniciando conversión e inventario…');try{const form=new FormData(event.currentTarget),csrf=form.get('csrfmiddlewaretoken');const response=await fetch('/catastro/api/planos/importar/',{method:'POST',body:form,credentials:'same-origin',headers:{'X-CSRFToken':csrf,Accept:'application/json'}});const value=await response.json();if(!response.ok)throw Error(value.error||'No se pudo registrar el DWG.');setStatus('DWG recibido. La lectura de capas está en proceso.');event.currentTarget.reset();setTimeout(()=>refresh($('plan-filter').elements.ubigeo.value.trim()),1800);}catch(error){setStatus(error.message,true);}finally{busy=false;button.disabled=false;}});
  refresh('');
})();
