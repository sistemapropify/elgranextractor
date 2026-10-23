(() => {
  'use strict';
  const PIPELINE=Object.freeze([
    {id:'intake',label:'Admisión de la fuente',detail:'Procedencia y ámbito declarados.',description:'Se registra el nombre de la fuente, distrito o UBIGEO, lámina o sector, fecha y tipo de aporte. El archivo entra como candidato y nunca se publica automáticamente.',result:'Fuente candidata identificada.',gate:'Conservar el original y su huella de integridad.'},
    {id:'original',label:'Original inmutable',detail:'Original recuperable y SHA-256.',description:'El PDF, DWG, JSON u otro archivo se archiva con SHA-256. Las correcciones crean una nueva versión y nunca sobrescriben el original anterior.',result:'Original recuperable y versión inmutable.',gate:'Inspeccionar formato, páginas, capas y contenido.'},
    {id:'inspection',label:'Inspección técnica',detail:'Estructura y calidad del archivo revisadas.',description:'Se revisan páginas o capas, tamaño, trazos, textos, entidades CAD, columnas o filas. También se identifica si un PDF es vectorial o escaneado.',result:'Inventario técnico del contenido.',gate:'Extraer o normalizar elementos utilizables.'},
    {id:'extraction',label:'Extracción o normalización',detail:'Elementos convertidos al contrato común.',description:'Se obtienen lotes, manzanas, lados, cotas, calles, direcciones o registros candidatos. El PDF usa inicialmente coordenadas locales; el DWG se convierte e inventaría; los registros se normalizan.',result:'Elementos candidatos con coordenadas o campos comunes.',gate:'Asignar significado a trazos y registros.'},
    {id:'semantic',label:'Clasificación semántica',detail:'Lotes, calles, registros y vínculos clasificados.',description:'Se determina qué representa cada trazo o registro: lote, manzana, calle, cota, texto, edificio, unidad, anuncio o identificador. Se revisan topología, rótulos y correspondencias visibles.',result:'Elementos clasificados y depurados como candidatos.',gate:'Declarar posición geográfica cuando corresponda.'},
    {id:'georef',label:'Georreferenciación',detail:'CRS, controles y error documentados.',description:'Se relacionan puntos del archivo con coordenadas de control y se calculan errores. La posición queda pendiente hasta revisar el CRS, la evidencia y comprobaciones independientes.',result:'Geometría con posición revisable.',gate:'Relacionar los elementos con identidades existentes.'},
    {id:'homologation',label:'Homologación de identidades',detail:'Elemento de fuente e inmueble relacionado.',description:'Cada lote o registro se enlaza con una entidad del maestro. No se fusionan inmuebles por cercanía, nombre o simple coincidencia; las diferencias de identidad se conservan.',result:'Mapa de correspondencias revisable.',gate:'Separar campos, procedencia, fechas y estados.'},
    {id:'normalization',label:'Normalización de campos y procedencia',detail:'Datos comparables con fuente y evidencia.',description:'Áreas, direcciones, usos, titulares, identificadores y demás datos se separan por fuente. Se conservan método, fecha y estado: candidato, observado, verificado, rechazado, sustituido o vencido.',result:'Campos comparables con procedencia completa.',gate:'Comparar antes de modificar el maestro.'},
    {id:'comparison',label:'Comparación previa',detail:'Efecto calculado sin aplicar cambios.',description:'Se muestra qué inmuebles, campos o geometrías cambiarían. Se puede completar vacíos, sustituir campos, reemplazar una capa en un ámbito o retirar el aporte de una fuente.',result:'Diferencia y token de revisión reproducibles.',gate:'Elegir el ámbito y confirmar la activación parcial.'},
    {id:'activation',label:'Revisión y activación parcial',detail:'Aporte revisado aplicado al maestro.',description:'Se aplica sólo el ámbito revisado. La fuente pasa a contribuyente, se actualizan las selecciones vigentes y el historial. Las identidades, documentos y originales no se eliminan.',result:'Información activa y reversible.',gate:'Verificar ficha, cobertura y consumidores.'},
    {id:'verification',label:'Ficha y verificación final',detail:'Resultado controlado en los módulos consumidores.',description:'Se comprueban datos, procedencia, documentos, fotografías, observaciones e historial en la ficha. La cobertura distingue qué está disponible, pendiente o desactualizado y qué debe revisarse.',result:'Resultado verificable en ficha, visor, ACM y Cuadrantización.',gate:'Mantener revisión, historial y cobertura actualizados.'},
  ]);
  const stageDefinition=id=>PIPELINE.find(stage=>stage.id===id)||PIPELINE[0];
  const recordFile=file=>/\.(?:json|geojson|ndjson|jsonl|csv|xlsx|xls)$/i.test(String(file.original_name||''));
  const fileKind=file=>recordFile(file)?'Datos':'PDF';
  const dataLotId=file=>{
    const match=String(file.source_id||'').match(/^cofopri-([0-9]{14})$/);
    return match?match[1]:null;
  };
  function pipelineStage(file){
    if(file.role==='backup')return 'backup';
    if(file.role==='contributing'&&Number(file.elements||0)>0)return 'activation';
    if(file.georeferencing?.status==='verified')return 'homologation';
    const vector=file.vector_review||{};
    const reviewApproved=['approved','reviewed','verified'].includes(String(vector.status||vector.review_status||''));
    if(reviewApproved)return 'georef';
    if(file.vector_review)return 'semantic';
    if(recordFile(file)&&Number(file.elements||0)>0)return 'normalization';
    if(file.original_available)return 'inspection';
    return 'original';
  }
  function dwgStage(file){
    return file.status==='completed'?'semantic':'inspection';
  }
  function consolidatePdfVersions(files){
    const groups=new Map();
    for(const file of files){
      const key=file.source_id||file.version_id;
      const rank=PIPELINE.findIndex(stage=>stage.id===pipelineStage(file));
      const current=groups.get(key);
      if(!current){groups.set(key,{...file,_rank:rank,_created:file.created_at||'',_versions:[file]});continue;}
      current._versions.push(file);
      current.original_available=current.original_available||file.original_available;
      const newer=rank>current._rank||(rank===current._rank&&String(file.created_at||'')>current._created);
      if(newer)groups.set(key,{...file,_rank:rank,_created:file.created_at||'',_versions:current._versions});
    }
    return [...groups.values()].map(item=>{
      const versions=item._versions||[item];
      return {...item,versions_count:versions.length,version_ids:versions.map(version=>version.version_id),
        version_labels:versions.map(version=>version.label)};
    });
  }
  function consolidateDwgCopies(rows){
    const groups=new Map();
    for(const row of rows){
      const key=row.sha256||row.id;
      if(!groups.has(key))groups.set(key,{...row,_copies:[row]});
      else groups.get(key)._copies.push(row);
    }
    return [...groups.values()].map(item=>({...item,copies:item._copies.length,
      copy_ids:item._copies.map(copy=>copy.id)}));
  }
  if(typeof module!=='undefined')module.exports={PIPELINE,pipelineStage,dwgStage,consolidatePdfVersions,consolidateDwgCopies};
  if(typeof document==='undefined')return;
  const root=document.getElementById('plan-hub');if(!root)return;
  const $=id=>document.getElementById(id),status=$('plan-status'),endpoint='/catastro/api/maestro/composicion/';let busy=false,revision=0,annotationsSupported=false,dataVersionCounts={};
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(cls)n.className=cls;return n;};
  function setStatus(text,error=false){status.textContent=text;status.dataset.error=String(error);}
  function csrf(){return $('dwg-form').elements.csrfmiddlewaretoken.value;}
  async function masterApi(payload=null,query=''){
    const response=await fetch(endpoint+query,{credentials:'same-origin',cache:'no-store',
      method:payload?'POST':'GET',headers:{Accept:'application/json',
        ...(payload?{'Content-Type':'application/json','X-CSRFToken':csrf()}:{})},
      ...(payload?{body:JSON.stringify(payload)}:{})});
    if(!response.headers.get('content-type')?.includes('application/json'))
      throw Error('Inicia sesión para administrar los planos.');
    const value=await response.json();
    if(!response.ok)throw Error(value.error||'No se pudo completar la acción.');
    if(Number.isInteger(value.revision))revision=value.revision;
    return value;
  }
  const dateTime=value=>{if(!value)return 'Sin fecha';const date=new Date(value);
    return Number.isNaN(date.getTime())?value:new Intl.DateTimeFormat('es-PE',
      {dateStyle:'short',timeStyle:'short',timeZone:'America/Lima'}).format(date);};
  function planProgress(item){
    const box=el('div',null,'plan-item-progress'),head=el('div',null,'plan-progress-head');
    if(item.stageCode==='backup'){
      head.append(el('span','Respaldo fuera de la ruta'),el('b','Sin avance'));
      box.append(head,el('p','No se cuenta como aporte activo ni como etapa pendiente.','plan-progress-note'));
      return box;
    }
    const index=PIPELINE.findIndex(stage=>stage.id===item.stageCode),number=Math.max(1,index+1);
    head.append(el('span','Etapa '+number+' de '+PIPELINE.length),el('b',item.stage));
    const track=el('div',null,'plan-progress-track');track.setAttribute('role','img');
    track.setAttribute('aria-label','Avance: '+number+' de '+PIPELINE.length+' etapas');
    PIPELINE.forEach((stage,stageIndex)=>{const mark=el('span',null,
      stageIndex+1<number?'done':stageIndex+1===number?'current':'pending');
      mark.title=(stageIndex+1)+' · '+stage.label;track.append(mark);});
    box.append(head,track,el('p','Resultado esperado: '+stageDefinition(item.stageCode).gate,'plan-progress-note'));
    return box;
  }
  function planThumbnail(item){
    const button=el('button',null,'plan-thumbnail');button.type='button';
    button.setAttribute('aria-label','Ampliar primera página de '+(item.name||item.original_name));
    const image=el('img');image.loading='lazy';image.alt='Miniatura de '+(item.name||item.original_name);
    image.src='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/pagina/?page=1';
    image.addEventListener('error',()=>{button.replaceWith(planPlaceholder(item));});
    button.append(image,el('span','Ver original'));
    button.addEventListener('click',()=>showPlanPreview(item));
    return button;
  }
  function planDataThumbnail(item){
    const button=el('button',null,'plan-thumbnail');button.type='button';
    button.setAttribute('aria-label','Ampliar fotografía del '+(item.name||item.lotId));
    const image=el('img');image.loading='lazy';image.alt='Fotografía catastral de '+(item.name||item.lotId);
    image.src='/catastro/api/maestro/planes/'+encodeURIComponent(item.version_id)+'/miniatura/';
    image.addEventListener('error',()=>{button.replaceWith(planPlaceholder(item));});
    button.append(image,el('span','Ver fotografía del lote'));
    button.addEventListener('click',()=>showDataPhoto(item,image.src));
    return button;
  }
  function planPlaceholder(item){
    const box=el('div',null,'plan-thumbnail plan-thumbnail-placeholder');
    const code=item.kind==='PDF'?'PDF':item.kind==='DWG'?'DWG':item.kind==='Datos'?'JSON':'DOC';
    box.append(el('span',code,'plan-placeholder-code'),el('b',item.name||item.filename||'Archivo sin título'),
      el('small','Sin miniatura disponible'));
    return box;
  }
  function openPlanDocument(item){
    if(item.kind==='PDF'&&item.vector_review&&item.original_available&&/\.pdf$/i.test(String(item.original_name||''))){
      showPlanPreview(item);return;
    }
    if(item.kind==='PDF'&&item.original_available){
      window.open('/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/original/','_blank','noopener');return;
    }
    if(item.kind==='DWG'&&item.status==='completed'){
      window.open('/catastro/visor-planos/?plano='+encodeURIComponent(item.id),'_blank','noopener');return;
    }
    if(item.kind==='Datos'&&item.lotId){
      window.open('/catastro/lotes/'+encodeURIComponent(item.lotId)+'/','_blank','noopener');return;
    }
    setStatus('Este archivo todavía no tiene una vista disponible.',true);
  }
  function legacyPlanFileActions(item,scope){
    const actions=el('div',null,'plan-item-actions plan-stage-file-actions');
    const open=el('button',item.kind==='Datos'?'Abrir ficha del lote':'Abrir plano');open.type='button';open.addEventListener('click',()=>openPlanDocument(item));actions.append(open);
    if(item.kind==='PDF'){
      const manage=el('a','Administrar fuente');manage.href='/catastro/maestro/fuentes/';actions.append(manage);
      if(item.original_available){
        const pdf=el('a','Abrir PDF');pdf.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/original/';
        pdf.target='_blank';pdf.rel='noopener';actions.append(pdf);
      }
      if(item.vector_review){
        const filename=Object.keys(item.vector_artifacts||{}).find(name=>name.endsWith('.geojson'));
        if(filename){const link=el('a','Descargar GeoJSON');link.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectores/'+encodeURIComponent(filename);link.download=filename;actions.append(link);}
      }else if(item.original_available&&item.stageCode==='inspection'){
        const button=el('button','Vectorizar PDF');button.type='button';button.addEventListener('click',async()=>{
          button.disabled=true;setStatus('Extrayendo trazos y texto del PDF…');
          try{
            const response=await fetch('/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectorizar/',{
              method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),Accept:'application/json'}});
            const value=await response.json();if(!response.ok)throw Error(value.error||'Falló la extracción vectorial.');
            setStatus(value.notice);await refresh(scope);
          }catch(error){setStatus(error.message,true);button.disabled=false;}
        });actions.append(button);
      }
      const calibrate=el('a','Calibrar posición');calibrate.href='/catastro/maestro/fuentes/#calibration-workspace';actions.append(calibrate);
      const homologate=el('a','Comparar / homologar');homologate.href='/catastro/maestro/fuentes/#sources-change-form';actions.append(homologate);
    }else if(item.kind==='DWG'){
      const link=el('a',item.status==='completed'?'Abrir visor CAD':'Ver estado');
      link.href=item.status==='completed'?'/catastro/visor-planos/?plano='+encodeURIComponent(item.id):
        '/catastro/api/planos/'+encodeURIComponent(item.id)+'/';
      if(item.status==='completed'){link.target='_blank';link.rel='noopener';}
      actions.append(link);
    }else{
      const manage=el('a','Administrar datos');manage.href='/catastro/maestro/fuentes/';actions.append(manage);
      if(item.lotId){const ficha=el('a','Ficha del lote');ficha.href='/catastro/lotes/'+encodeURIComponent(item.lotId)+'/';ficha.target='_blank';ficha.rel='noopener';actions.append(ficha);}
      const homologate=el('a','Usar en el maestro');homologate.href='/catastro/maestro/fuentes/#sources-change-form';actions.append(homologate);
    }
    if(annotationsSupported){
      const titleButton=el('button','Editar título','secondary');titleButton.type='button';
      titleButton.addEventListener('click',()=>editPlanTitle(item));actions.prepend(titleButton);
      const notesButton=el('button','Notas ('+item.noteCount+')','secondary');notesButton.type='button';
      notesButton.addEventListener('click',()=>{
        const row=actions.closest('.plan-stage-file')||actions.parentElement;
        togglePlanNotes(item,row,notesButton);
      });actions.append(notesButton);
    }
    return actions;
  }
  function planFileActions(item,scope){
    const groups=el('div',null,'plan-action-groups');
    const group=(title)=>{
      const box=el('section',null,'plan-action-group');
      box.append(el('h5',title));
      groups.append(box);
      return box;
    };
    const addLink=(host,label,href,download)=>{
      const link=el('a',label);link.href=href;
      if(['PDF','Datos'].includes(item.kind)||item.status==='completed'){link.target='_blank';link.rel='noopener';}
      if(download)link.download=download;
      host.append(link);
    };
    const addButton=(host,label,handler)=>{
      const button=el('button',label,'secondary');button.type='button';
      button.addEventListener('click',handler);host.append(button);return button;
    };
    const documentGroup=group('Documento');
    if(item.kind==='PDF'){
      addButton(documentGroup,'Abrir plano',()=>openPlanDocument(item));
      addLink(documentGroup,'Administrar fuente','/catastro/maestro/fuentes/');
      if(item.original_available)addLink(documentGroup,'Abrir PDF',
        '/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/original/');
    }else if(item.kind==='Datos'){
      if(item.lotId)addButton(documentGroup,'Abrir ficha del lote',()=>openPlanDocument(item));
      addLink(documentGroup,'Administrar datos','/catastro/maestro/fuentes/');
    }else{
      addLink(documentGroup,item.status==='completed'?'Abrir visor CAD':'Ver estado',
        item.status==='completed'?'/catastro/visor-planos/?plano='+encodeURIComponent(item.id):
          '/catastro/api/planos/'+encodeURIComponent(item.id)+'/');
    }
    const processGroup=group('Proceso');
    if(item.kind==='PDF'){
      if(!item.vector_review&&item.original_available&&item.stageCode==='inspection'){
        addButton(processGroup,'Vectorizar PDF',async()=>{
          try{
            const response=await fetch('/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectorizar/',{
              method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),Accept:'application/json'}});
            const value=await response.json();if(!response.ok)throw Error(value.error||'Falló la extracción vectorial.');
            setStatus(value.notice);await refresh(scope);
          }catch(error){setStatus(error.message,true);}
        });
      }
      addLink(processGroup,'Calibrar posición','/catastro/maestro/fuentes/#calibration-workspace');
      addLink(processGroup,'Comparar / homologar','/catastro/maestro/fuentes/#sources-change-form');
    }else if(item.kind==='Datos'){
      addLink(processGroup,'Usar datos en el maestro','/catastro/maestro/fuentes/#sources-change-form');
    }else{
      addLink(processGroup,'Homologar capas','/catastro/maestro/fuentes/#sources-change-form');
    }
    if(annotationsSupported){
      const follow=group('Seguimiento');
      addButton(follow,'Editar título',()=>editPlanTitle(item));
      const notesButton=addButton(follow,'Notas ('+item.noteCount+')',()=>{
        const host=groups.closest('.plan-stage-file-content')||groups.parentElement;
        togglePlanNotes(item,host,notesButton);
      });
    }
    return groups;
  }
  function showPlanPreview(item){
    const dialog=el('dialog',null,'plan-preview-dialog'),close=el('button','Cerrar ×','plan-dialog-close');
    close.type='button';close.addEventListener('click',()=>dialog.close());
    const image=el('img');image.alt='Original PDF de '+(item.name||item.original_name);
    image.src='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/pagina/?page=1';
    const link=el('a','Abrir PDF original');
    link.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/original/';
    link.target='_blank';link.rel='noopener';
    dialog.append(close,el('h2',item.name||item.original_name),image,link);
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
    dialog.addEventListener('close',()=>dialog.remove());
    document.body.append(dialog);dialog.showModal();
  }
  function showDataPhoto(item,src){
    const dialog=el('dialog',null,'plan-preview-dialog'),close=el('button','Cerrar ×','plan-dialog-close');
    close.type='button';close.addEventListener('click',()=>dialog.close());
    const image=el('img');image.alt='Fotografía catastral de '+(item.name||item.lotId);image.src=src;
    const link=el('a','Abrir ficha del lote');link.href='/catastro/lotes/'+encodeURIComponent(item.lotId)+'/';
    link.target='_blank';link.rel='noopener';
    dialog.append(close,el('h2',item.name||('Lote '+item.lotId)),image,link);
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
    dialog.addEventListener('close',()=>dialog.remove());
    document.body.append(dialog);dialog.showModal();
  }
  function editPlanTitle(item){
    const dialog=el('dialog',null,'plan-title-dialog'),form=el('form'),label=el('label','Título del plano');
    const input=el('input');input.required=true;input.maxLength=300;input.value=item.name||'';
    label.append(input);
    const actions=el('div',null,'plan-dialog-actions'),cancel=el('button','Cancelar','secondary'),save=el('button','Guardar título');
    cancel.type='button';save.type='submit';
    cancel.addEventListener('click',()=>dialog.close());
    actions.append(cancel,save);form.append(el('h2','Editar título'),el('p','Este título organiza el plano y no modifica el nombre del archivo original.'),label,actions);
    form.addEventListener('submit',async event=>{event.preventDefault();save.disabled=true;
      try{await masterApi({action:'plan_title',document_key:item.documentKey,document_type:item.documentType,
        source_version:item.documentType!=='dwg'?item.version_id:null,
        scope_ubigeo:item.scopeUbigeo,title:input.value,revision});
        dialog.close();setStatus('Título del plano actualizado.');await refresh($('plan-filter').elements.ubigeo.value.trim());
      }catch(error){setStatus(error.message,true);save.disabled=false;}});
    dialog.addEventListener('close',()=>dialog.remove());dialog.append(form);document.body.append(dialog);dialog.showModal();
  }
  async function loadPlanNotes(item,box,button){
    const data=await masterApi(null,'?'+new URLSearchParams({view:'plan_notes',document_key:item.documentKey}));
    box.replaceChildren(el('h4','Notas y comentarios'),el('p','Cada nota conserva fecha y autor. No modifica el plano original ni activa datos.','plan-note-help'));
    if(!data.items.length)box.append(el('p','Este plano todavía no tiene notas.','plan-note-empty'));
    for(const note of data.items){const entry=el('article',null,'plan-note');entry.append(el('time',dateTime(note.created_at)),el('p',note.note),el('small',note.actor));box.append(entry);}
    const form=el('form',null,'plan-note-form'),textarea=el('textarea');textarea.rows=3;textarea.maxLength=4000;textarea.required=true;textarea.placeholder='Agregar una observación sobre este plano…';
    const add=el('button','Agregar nota');add.type='submit';form.append(textarea,add);
    form.addEventListener('submit',async event=>{event.preventDefault();add.disabled=true;
      try{await masterApi({action:'plan_note',document_key:item.documentKey,document_type:item.documentType,
        source_version:item.documentType!=='dwg'?item.version_id:null,
        scope_ubigeo:item.scopeUbigeo,note:textarea.value,revision});
        item.noteCount+=1;button.textContent='Notas ('+item.noteCount+')';setStatus('Nota agregada al plano con fecha y autor.');await loadPlanNotes(item,box,button);
      }catch(error){setStatus(error.message,true);add.disabled=false;}});
    box.append(form);box.dataset.loaded='true';
  }
  async function togglePlanNotes(item,card,button){
    let box=card.querySelector('.plan-notes');
    const existed=!!box;
    if(!box){box=el('section',null,'plan-notes');box.hidden=true;card.append(box);}
    if(existed&&!box.hidden){box.hidden=true;button.textContent='Notas ('+item.noteCount+')';return;}
    box.hidden=false;button.textContent='Ocultar notas';
    if(!box.dataset.loaded){box.replaceChildren(el('p','Consultando notas…'));try{await loadPlanNotes(item,box,button);}catch(error){box.replaceChildren(el('p',error.message,'plan-note-error'));}}
  }
  function render(portfolio,dwgRows,scope,annotations={}){
    let files=(portfolio.files||[]).filter(x=>x.version_id&&!recordFile(x));
    let cad=dwgRows||[];
    if(scope){files=files.filter(x=>x.ubigeo===scope);cad=cad.filter(x=>x.ubigeo===scope);}
    files=consolidatePdfVersions(files);
    cad=consolidateDwgCopies(cad);
    const decorated=files.map(file=>{const stage=pipelineStage(file),definition=stageDefinition(stage),documentKey='source:'+file.source_id,note=annotations[documentKey]||{},lotId=dataLotId(file),kind=fileKind(file);return {...file,kind,lotId,documentKey,documentType:'source',sourceVersion:file.version_id,scopeUbigeo:file.ubigeo||'040103',stageCode:stage,stage:stage==='backup'?'Respaldo':definition.label,detail:stage==='backup'?'Respaldo retenido y excluido de la ruta de activación.':definition.detail+(file.versions_count>1?` · ${file.versions_count} versiones consolidadas`:''),name:note.display_title||(lotId?'Lote '+lotId:(file.original_name||file.filename)),noteCount:Number(note.note_count||0)};});
    const dwg=cad.map(file=>{const stage=dwgStage(file),definition=stageDefinition(stage),documentKey='dwg:'+(file.sha256?'sha-'+file.sha256:file.id),note=annotations[documentKey]||{};return {...file,kind:'DWG',documentKey,documentType:'dwg',scopeUbigeo:file.ubigeo||scope||'040103',name:note.display_title||((file.source_name||file.filename)+' · '+(file.sheet_code||'sin lámina')),stageCode:stage,stage:definition.label,detail:(file.status==='completed'?`${file.drawable||0} entidades dibujables · ${file.layer_count??file.layers?.length??0} capas · unidades CAD ${file.units??'sin definir'}`:file.message||'Conversión en proceso')+(file.copies>1?` · ${file.copies} copias idénticas consolidadas`:''),noteCount:Number(note.note_count||0)};});
    const all=[...decorated,...dwg];
    const workflowFiles=all.filter(x=>x.stageCode!=='backup');
    const counts=Object.fromEntries(PIPELINE.map(stage=>[stage.id,workflowFiles.filter(item=>item.stageCode===stage.id).length]));
    const activeRows=portfolio.active_by_district||[];const active=activeRows.filter(x=>!scope||x.ubigeo===scope).reduce((n,x)=>n+Number(x.geometries||0),0);
    const projects=(portfolio.projects||[]).filter(x=>!scope||x.ubigeo===scope);
    $('plan-stats').replaceChildren(...[[all.length,'Planos registrados en el ámbito'],[decorated.length,'Versiones PDF'],[counts.inspection,'Archivos por inspeccionar'],[dwg.length,'DWG locales registrados'],[dwg.filter(x=>x.status==='completed').length,'DWG con capas leídas'],[active,'Geometrías activas del maestro'],[projects.reduce((n,p)=>n+Number(p.expected_sheets||0),0),'Láminas previstas en proyectos']].map(([value,label])=>{const card=el('article',null,'plan-stat');card.append(el('strong',value),el('span',label));return card;}));
    const stages=$('plan-stages'),backups=decorated.filter(x=>x.stageCode==='backup').length;
    stages.replaceChildren(...PIPELINE.map((stage,index)=>{
      const stageFiles=workflowFiles.filter(item=>item.stageCode===stage.id),value=stageFiles.length;
      const reached=workflowFiles.filter(item=>PIPELINE.findIndex(definition=>definition.id===item.stageCode)>=index).length;
      const card=el('details',null,'plan-stage'+(value?' has-work':'')+(index<2?' base':''));
      card.open=value>0;
      const summary=el('summary'),heading=el('div',null,'plan-stage-heading');
      heading.append(el('small',`${value} archivos aquí · ${reached} alcanzaron`, 'plan-stage-count'),el('b',stage.label));
      summary.append(el('span',String(index+1).padStart(2,'0'),'plan-stage-index'),heading);card.append(summary);
      const body=el('div',null,'plan-stage-body');
      body.append(el('p',stage.description,'plan-stage-description'),el('p',stage.result,'plan-stage-output'),el('p',stage.gate,'plan-stage-gate'));
      const list=el('div',null,'plan-stage-files'),listTitle=el('h4',value?`Archivos en ${stage.label}`:'No hay archivos en esta etapa');
      list.append(listTitle);
      if(stageFiles.length)for(const item of stageFiles){
        const row=el('div',null,'plan-stage-file');
        const visual=el('div',null,'plan-stage-file-visual');
        const content=el('div',null,'plan-stage-file-content');
        const fileName=el('button',item.kind+' · '+(item.name||item.filename),'plan-stage-file-name');
        fileName.type='button';fileName.title='Abrir '+(item.name||item.filename);
        fileName.addEventListener('click',()=>openPlanDocument(item));
        content.append(fileName,el('small',item.detail||''));
        if(item.kind==='PDF'&&item.original_available&&/\.pdf$/i.test(String(item.original_name||'')))visual.append(planThumbnail(item));
        else if(item.kind==='Datos'&&item.lotId)visual.append(planDataThumbnail(item));
        else visual.append(planPlaceholder(item));
        content.append(planFileActions(item,scope));
        row.append(visual,content);
        list.append(row);
      }else list.append(el('p','Los archivos que ya superaron esta etapa aparecen en su etapa actual.','plan-stage-empty'));
      body.append(list);card.append(body);return card;
    }));
    if(backups)stages.append(el('p',`${backups} respaldo${backups===1?'':'s'} conservado${backups===1?'':'s'} fuera de la ruta. No se presentan como aportes activos ni avanzan por estas etapas.`,'plan-stage-backup'));
    const districtMap=new Map();const district=key=>{if(!districtMap.has(key))districtMap.set(key,{ubigeo:key,pdf:0,pending:0,review:0,verified:0,applied:0,dwg:0,active:0});return districtMap.get(key);};
    for(const f of decorated){const d=district(f.ubigeo||'Sin UBIGEO');d.pdf++;if(f.stageCode==='inspection'||f.stageCode==='extraction')d.pending++;if(f.stageCode==='semantic')d.review++;if(f.georeferencing?.status==='verified')d.verified++;if(f.stageCode==='activation')d.applied++;}
    for(const f of dwg){district(f.ubigeo||'Sin UBIGEO').dwg++;}
    for(const f of activeRows)if(!scope||f.ubigeo===scope)district(f.ubigeo).active=Number(f.geometries||0);
    const hostDistricts=$('plan-districts');hostDistricts.replaceChildren();
    if(districtMap.size){const table=el('table'),thead=el('thead'),head=el('tr');for(const title of ['UBIGEO','PDF','Por vectorizar','En revisión','Posición verificada','Aportes activos','DWG','Geometrías activas'])head.append(el('th',title));thead.append(head);table.append(thead);const body=el('tbody');for(const d of [...districtMap.values()].sort((a,b)=>a.ubigeo.localeCompare(b.ubigeo))){const row=el('tr');for(const val of [d.ubigeo,d.pdf,d.pending,d.review,d.verified,d.applied,d.dwg,d.active])row.append(el('td',val));body.append(row);}table.append(body);hostDistricts.append(table);}
    for(const project of projects){const p=el('p',`${project.name} · ${project.registered_sheets||0} / ${project.expected_sheets||0} láminas registradas · ${project.ubigeo}`,'plan-project-progress');hostDistricts.append(p);}
    const host=$('plan-inventory');host.replaceChildren();if(!all.length){host.append(el('p','No hay PDF ni DWG registrados para este ámbito. Los archivos que no se han incorporado al gestor no aparecen en este inventario.','plan-empty'));return;}
    for(const item of all){const card=el('article',null,'plan-item');card.append(el('span',item.kind+' · '+item.stage,'plan-pill'),el('h3',item.name||item.filename),el('p',item.detail));
      if(item.kind==='PDF'){card.append(el('p',`UBIGEO ${item.ubigeo||'—'} · ${item.sheet_code||'sin lámina'} · ${item.elements||0} atributos preparados · ${item.georeferencing?.status||'posición pendiente'} · ${item.original_name||'nombre original no registrado'}`));if(item.vector_review)card.append(el('p',`${item.vector_review.vector_paths||0} trazos · ${item.vector_review.text_words||0} palabras · ${item.vector_review.coordinate_space||'coordenadas locales'} · ningún lote identificado automáticamente`));}
      else card.append(el('p',`UBIGEO ${item.ubigeo||'sin asignar'} · ${item.filename||''} · SHA256 ${item.sha256||'pendiente'}`));
      card.append(planProgress(item));
      if(item.kind==='PDF'&&item.original_available&&/\.pdf$/i.test(String(item.original_name||'')))card.append(planThumbnail(item));
      const actions=el('div',null,'plan-item-actions');
      if(item.kind==='PDF'){const manage=el('a','Administrar fuente');manage.href='/catastro/maestro/fuentes/';actions.append(manage);if(item.original_available){const pdf=el('a','Abrir PDF');pdf.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/original/';pdf.target='_blank';pdf.rel='noopener';actions.append(pdf);}if(item.vector_review){const filename=Object.keys(item.vector_artifacts||{}).find(x=>x.endsWith('.geojson'));if(filename){const link=el('a','Descargar GeoJSON');link.href='/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectores/'+encodeURIComponent(filename);link.download=filename;actions.append(link);}}else if(item.original_available&&item.stageCode==='inspection'){const button=el('button','Vectorizar PDF');button.type='button';button.addEventListener('click',async()=>{button.disabled=true;setStatus('Extrayendo trazos y texto del PDF…');try{const csrf=$('dwg-form').elements.csrfmiddlewaretoken.value;const response=await fetch('/catastro/api/maestro/pdf/'+encodeURIComponent(item.version_id)+'/vectorizar/',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf,Accept:'application/json'}});const value=await response.json();if(!response.ok)throw Error(value.error||'Falló la extracción vectorial.');setStatus(value.notice);await refresh(scope);}catch(error){setStatus(error.message,true);button.disabled=false;}});actions.append(button);}const calibrate=el('a','Calibrar posición');calibrate.href='/catastro/maestro/fuentes/#calibration-workspace';actions.append(calibrate);const homologate=el('a','Comparar / homologar');homologate.href='/catastro/maestro/fuentes/#sources-change-form';actions.append(homologate);}
      else{const link=el('a',item.status==='completed'?'Abrir visor CAD':'Ver estado');link.href=item.status==='completed'?'/catastro/visor-planos/?plano='+encodeURIComponent(item.id):'/catastro/api/planos/'+encodeURIComponent(item.id)+'/';link.target=item.status==='completed'?'_blank':'_self';actions.append(link);}
      if(annotationsSupported){const titleButton=el('button','Editar título','secondary');titleButton.type='button';titleButton.addEventListener('click',()=>editPlanTitle(item));actions.prepend(titleButton);
        const notesButton=el('button','Notas ('+item.noteCount+')','secondary');notesButton.type='button';notesButton.addEventListener('click',()=>togglePlanNotes(item,card,notesButton));actions.append(notesButton);}
      card.append(actions);host.append(card);
    }
  }
  async function refresh(scope){
    if(busy)return;
    busy=true;
    setStatus('Consultando el catálogo de todos los distritos y los DWG locales…');
    try{
      const [portfolioResponse,cadResponse]=await Promise.all([
        fetch('/catastro/api/maestro/planos/',{credentials:'same-origin',cache:'no-store'}),
        fetch('/catastro/api/planos/inventario/',{credentials:'same-origin',cache:'no-store'}),
      ]);
      const portfolio=await portfolioResponse.json(),cad=await cadResponse.json();
      if(!portfolioResponse.ok)throw Error(portfolio.error||'No se pudo consultar el maestro.');
      if(!cadResponse.ok)throw Error(cad.error||'No se pudo consultar el inventario CAD.');
      const keys=[
        ...consolidatePdfVersions((portfolio.files||[]).filter(file=>file.version_id&&!recordFile(file))).map(file=>'source:'+file.source_id),
        ...consolidateDwgCopies(cad.dwg||[]).map(file=>'dwg:'+(file.sha256?'sha-'+file.sha256:file.id)),
      ];
      dataVersionCounts={};
      for(const file of (portfolio.files||[]).filter(recordFile))
        dataVersionCounts[file.ubigeo]=(dataVersionCounts[file.ubigeo]||0)+1;
      const selectedDataDistrict=document.querySelector('[name="data_ubigeo"]')?.value;
      if(selectedDataDistrict){
        try{
          const migrationResponse=await fetch('/catastro/api/maestro/migracion/?ubigeo='+encodeURIComponent(selectedDataDistrict),{credentials:'same-origin',cache:'no-store'});
          const migration=await migrationResponse.json();
          if(!migrationResponse.ok)throw Error(migration.error||'No se pudo consultar la vinculación al maestro.');
          if($('geollaqta-indexed'))$('geollaqta-indexed').textContent=Number(migration.linked_lots||0).toLocaleString('es-PE');
          if($('geollaqta-pending'))$('geollaqta-pending').textContent=Number(migration.pending_lots||0).toLocaleString('es-PE');
        }catch(error){setStatus(error.message,true);}
      }
      let annotations={};
      if(keys.length){
        const result=await masterApi(null,'?'+new URLSearchParams({view:'plan_annotations',keys:keys.join(',')}));
        annotationsSupported=Object.hasOwn(result,'annotations');
        annotations=annotationsSupported?result.annotations||{}:{};
      }
      render(portfolio,cad.dwg,scope,annotations);
      setStatus((portfolio.truncated?'Catálogo limitado a 5000 versiones. ':'')+
        'Inventario listo. Los archivos y sus propuestas siguen separados de los lotes aprobados.');
    }catch(error){
      setStatus(error.message,true);
    }finally{
      busy=false;
    }
  }
  $('plan-filter').addEventListener('submit',event=>{event.preventDefault();refresh($('plan-filter').elements.ubigeo.value.trim());});$('plan-refresh').addEventListener('click',()=>refresh($('plan-filter').elements.ubigeo.value.trim()));
  $('dwg-form').addEventListener('submit',async event=>{event.preventDefault();if(busy)return;busy=true;const button=event.currentTarget.querySelector('button[type=submit]');button.disabled=true;setStatus('Subiendo DWG e iniciando conversión e inventario…');try{const form=new FormData(event.currentTarget),csrf=form.get('csrfmiddlewaretoken');const response=await fetch('/catastro/api/planos/importar/',{method:'POST',body:form,credentials:'same-origin',headers:{'X-CSRFToken':csrf,Accept:'application/json'}});const value=await response.json();if(!response.ok)throw Error(value.error||'No se pudo registrar el DWG.');setStatus('DWG recibido. La lectura de capas está en proceso.');event.currentTarget.reset();setTimeout(()=>refresh($('plan-filter').elements.ubigeo.value.trim()),1800);}catch(error){setStatus(error.message,true);}finally{busy=false;button.disabled=false;}});
  refresh('');
})();
