(() => {
  'use strict';
  const $ = id => document.getElementById(id), form = $('cmp-form'), presentation = window.ACMComponentsPresentation;
  let snapshot=null, result=null, excluded=new Set(), tab='Casa', map=null, pin=null, circles=[], markers=[], sequence=0, controller=null, detailId=null;
  const money=n=>n==null?'—':new Intl.NumberFormat('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
  const decimals=n=>n==null?'Sin informar':new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(n);
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function input(){return {property_type:form.elements.property_type.value,rooms:form.elements.rooms.disabled?null:form.elements.rooms.value,baths:form.elements.baths.disabled?null:form.elements.baths.value,floor:form.elements.floor.disabled?null:form.elements.floor.value,lat:Number(form.elements.lat.value),lng:Number(form.elements.lng.value),land:Number(form.elements.land.value),built:Number(form.elements.built.value),radius:Number(form.elements.radius.value),max_radius:Number(form.elements.max_radius.value),sources:Array.from(form.querySelectorAll('[name=source]:checked'),x=>x.value)};}
  function configureType(){
    const type=form.elements.property_type.value,house=type==='Casa',land=type==='Terreno';
    [['land',house||land],['built',!land],['rooms',house||type==='Departamento'],['baths',!land],['floor',!house&&!land]].forEach(([key,show])=>{
      $('cmp-'+key+'-field').hidden=!show;form.elements[key].disabled=!show;
      if(key==='land'||key==='built')form.elements[key].required=show;
    });
    $('cmp-expansion-field').hidden=!house;
    $('cmp-method-label').textContent=house?'Casa: suelo + construcción y mejoras':land?'Terreno: comparables de suelo':'Comparables de '+type.toLowerCase()+' por superficie construida';
    $('cmp-map-explanation').textContent=house?'Suelo estimado con terrenos; construcción y mejoras como remanente del anuncio.':'Solo se calculan comparables completos del tipo seleccionado dentro del radio elegido.';
    document.querySelector('[data-tab="Casa"]').hidden=land;
    document.querySelector('[data-tab="Terreno"]').hidden=!house&&!land;
    const mode=$('cmp-marker-mode');mode.options[0].textContent=house||land?'Suelo / m²':'Oferta / m² construido';mode.options[1].disabled=!house;if(!house&&mode.value==='improvements')mode.value='land';
    const propertyLayer=document.querySelector('[name=map_layer][value=property]'),landLayer=document.querySelector('[name=map_layer][value=land]'),propertyReferenceLayer=document.querySelector('[name=map_layer][value=property_reference]'),otherReferenceLayer=document.querySelector('[name=map_layer][value=other_reference]');
    propertyLayer.checked=!land;landLayer.checked=land;propertyReferenceLayer.checked=false;otherReferenceLayer.checked=false;
    propertyLayer.closest('label').hidden=land;propertyReferenceLayer.closest('label').hidden=land;
    landLayer.closest('label').hidden=!house&&!land;otherReferenceLayer.closest('label').hidden=!house&&!land;
    $('cmp-property-layer-label').textContent=house?'Casas comparables':type+'s comparables';
    $('cmp-property-reference-layer-label').textContent=house?'Casas solo referencia':type+'s solo referencia';
    $('cmp-land-layer-label').textContent=house?'Terrenos para valor del suelo':'Terrenos comparables';
    $('cmp-other-reference-layer-label').textContent=land?'Terrenos solo referencia':'Terrenos no usados';
    if(map&&result)renderMap();
  }
  async function post(path,data){
    if(controller)controller.abort();controller=new AbortController();const current=controller;
    const timer=setTimeout(()=>current.abort(),45000);
    try{const response=await fetch(path==='buscar'?form.dataset.searchUrl:form.dataset.calculateUrl,{method:'POST',credentials:'same-origin',signal:current.signal,headers:{'Content-Type':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value},body:JSON.stringify(data)});
      if(!response.headers.get('content-type')?.includes('application/json'))throw Error('El servidor no devolvió datos. Comprueba tu sesión y vuelve a intentar.');
      const body=await response.json();if(!response.ok)throw Error(body.error||'No se pudo completar la consulta.');return body;
    }catch(e){if(e.name==='AbortError')throw Error('La consulta se canceló o superó 45 segundos. Puedes reintentar.');throw e;}finally{clearTimeout(timer);}
  }
  function clearMap(){markers.forEach(m=>m.setMap(null));markers=[];}
  function drawCircles(){
    if(!map)return;circles.forEach(c=>c.setMap(null));circles=[];
    const p=snapshot?.params||input(),center={lat:p.lat,lng:p.lng};if(!Number.isFinite(center.lat)||!Number.isFinite(center.lng))return;
    if(!pin)pin=new google.maps.Marker({map,position:center,title:'Inmueble objetivo',draggable:true});else pin.setPosition(center);
    if(!pin.cmpListener){pin.addListener('dragend',e=>setLocation(e.latLng.lat(),e.latLng.lng()));pin.cmpListener=true;}
    circles.push(new google.maps.Circle({map,center,radius:p.radius,strokeColor:'#4597ec',strokeWeight:2,fillColor:'#4597ec',fillOpacity:.08}));
    if(result?.land_radius>p.radius)circles.push(new google.maps.Circle({map,center,radius:result.land_radius,strokeColor:'#e8b455',strokeWeight:2,fillOpacity:0}));
  }
  function clearResult(message){
    result=null;clearMap();drawCircles();$('cmp-export').disabled=true;
    $('cmp-new').innerHTML='<h2>Valoración por componentes</h2><p class="cmp-muted">'+escape(message)+'</p>';
    $('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>—</strong>';
    $('cmp-map-count').textContent='Sin análisis vigente';
    if(snapshot){renderCards();renderDetail();}else{$('cmp-cards').innerHTML='<p class="cmp-muted">Busca comparables para aplicar el análisis.</p>';$('cmp-counts').textContent='Sin comparables';['house','land','ref'].forEach(k=>$('cmp-'+k+'-count').textContent='');}
  }
  function invalidate(){
    sequence++;if(controller)controller.abort();snapshot=null;excluded.clear();if($('cmp-detail').open)$('cmp-detail').close();
    clearResult('Parámetros modificados: vuelve a buscar.');$('cmp-warnings').replaceChildren();$('cmp-status').textContent='Listo para una nueva búsqueda.';$('cmp-search').disabled=false;
  }
  function setLocation(lat,lng){form.elements.lat.value=lat.toFixed(7);form.elements.lng.value=lng.toFixed(7);invalidate();if(map)map.panTo({lat,lng});}
  window.initComponentMap=()=>{
    const p=input();map=new google.maps.Map($('cmp-map'),{center:{lat:p.lat,lng:p.lng},zoom:15,mapTypeControl:false,streetViewControl:false});map.addListener('click',e=>setLocation(e.latLng.lat(),e.latLng.lng()));
    const auto=new google.maps.places.Autocomplete($('cmp-address'),{fields:['geometry','formatted_address'],componentRestrictions:{country:'pe'}});
    auto.addListener('place_changed',()=>{const place=auto.getPlace();if(place.geometry){setLocation(place.geometry.location.lat(),place.geometry.location.lng());map.setZoom(16);}});drawCircles();if(snapshot&&result)renderMap();
  };
  window.gm_authFailure=()=>{$('cmp-status').textContent='No se pudo cargar Google Maps. Puedes ingresar latitud y longitud para buscar.';};
  // Keep all consulted records visible so an excluded outer land can be selected again.
  function visibleRows(){return snapshot?.records||[];}
  const value=r=>presentation.property(r,result,excluded);
  const mapGroup=r=>presentation.group(r,value(r));
  function visibleMapRows(){const layers=new Set(Array.from(document.querySelectorAll('[name=map_layer]:checked'),x=>x.value));return visibleRows().filter(r=>layers.has(mapGroup(r)));}
  function renderMap(){
    if(!map||!result)return;clearMap();drawCircles();
    const icons={propify:'Pin-propify.png',remax:'pin-remax.png',properati:'pin-properati.png'};
    const mode=$('cmp-marker-mode').value;
    const rows=visibleMapRows();
    rows.forEach(r=>{
      const v=value(r),label=presentation.marker(r,v,mode),dim=['reference','excluded','pending'].includes(v.status);
      const icon=icons[r.source]?{url:'/static/requerimientos/data/'+icons[r.source],scaledSize:new google.maps.Size(32,40),anchor:new google.maps.Point(16,40),labelOrigin:new google.maps.Point(16,52)}:{path:google.maps.SymbolPath.CIRCLE,scale:7,fillColor:r.kind==='Terreno'?'#d6a548':'#3789dd',fillOpacity:1,strokeColor:'#ffffff',strokeWeight:1,labelOrigin:new google.maps.Point(0,3)};
      const marker=new google.maps.Marker({map,position:{lat:r.lat,lng:r.lng},title:r.title+' · '+presentation.precision(r).label+' · '+label,opacity:dim?.55:1,icon,label:{text:label,fontSize:'10px',fontWeight:'600',className:'cmp-pin-label'}});
      marker.addListener('click',()=>openDetail(r.id));markers.push(marker);
    });
    $('cmp-map-count').textContent=rows.length+' visibles de '+visibleRows().length;
  }
  function renderSummary(){
    const r=result,n=r.new,validSoil=r.land_unit!=null;
    const targetRows=visibleRows().filter(row=>row.kind===snapshot.params.property_type),usedRows=targetRows.filter(row=>mapGroup(row)===(snapshot.params.property_type==='Terreno'?'land':'property'));
    let diagnostic='';
    if(!usedRows.length&&targetRows.length){
      const counts=new Map();targetRows.forEach(row=>row.issues.forEach(issue=>counts.set(issue,(counts.get(issue)||0)+1)));
      const reasons=[...counts].sort((a,b)=>b[1]-a[1]).slice(0,4).map(([reason,count])=>count+' × '+reason);
      diagnostic='<div class="cmp-warning"><strong>0 '+escape(snapshot.params.property_type.toLowerCase())+'s aptas de '+targetRows.length+' encontradas.</strong>'+(reasons.length?'<br>Principales motivos: '+reasons.map(escape).join(' · '):' Revisa los datos y la selección manual.')+'</div>';
    }
    $('cmp-warnings').innerHTML=diagnostic+snapshot.warnings.concat(result.new?result.messages:[]).map(w=>'<div class="cmp-warning">'+escape(w)+'</div>').join('');
    if(r.model!=='components'){
      const basis=r.model==='land'?'terreno':'superficie construida';
      $('cmp-new').innerHTML='<h2>Valoración · '+escape(r.property_type)+'</h2><p class="cmp-muted">'+(r.house_count+r.land_count)+' comparables seleccionados</p>'+(n?'<div class="cmp-line"><span>Mediana por m² de '+basis+'</span><strong>'+money(n.unit)+'/m²</strong></div><div class="cmp-total">'+money(n.total)+'</div><p class="cmp-muted">'+decimals(snapshot.params[n.area_basis])+' m² × '+money(n.unit)+'/m²<br>Rango orientativo: '+money(n.range_low)+' – '+money(n.range_high)+'</p><div class="cmp-difference">Frente al anterior: '+money(n.delta)+' ('+decimals(n.delta_pct)+'%)</div>':'<p class="cmp-warning">'+r.messages.map(escape).join('<br>')+'</p>');
      $('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>'+money(r.old?.total)+'</strong><small>Promedio ponderado por distancia sobre la misma superficie y selección.</small>';return;
    }
    const usedHouses=Number.isFinite(r.usable_house_count)?r.usable_house_count:0;
    $('cmp-new').innerHTML='<h2>Valoración por componentes</h2><p class="cmp-muted">'+r.land_count+' terrenos usados · '+usedHouses+' casas usadas · suelo hasta '+r.land_radius+' m</p>'+
      (validSoil?'<div class="cmp-line"><span>Suelo de la microzona</span><strong>'+money(r.land_unit)+'/m²</strong></div>':'')+
      (n?'<div class="cmp-line"><span>Terreno objetivo</span><strong>'+money(n.land_value)+'</strong></div><div class="cmp-line"><span>Construcción y mejoras</span><strong>'+money(n.built_value)+'</strong></div><div class="cmp-total">'+money(n.total)+'</div><p class="cmp-muted">Aporte de mejoras: '+money(n.built_unit)+'/m² construido.<br>Rango central orientativo: '+money(n.range_low)+' – '+money(n.range_high)+'.</p><div class="cmp-difference">Frente al anterior: '+(n.delta>=0?'+':'')+money(n.delta)+' ('+(n.delta_pct>=0?'+':'')+decimals(n.delta_pct)+'%)</div>':'<p class="cmp-warning">'+r.messages.map(escape).join('<br>')+'</p>');
    $('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>'+money(r.old?.total)+'</strong><small>'+(r.old?money(r.old.unit)+'/m² construido<br>':'')+'Mismas casas seleccionadas. Solo comparación; no alimenta el nuevo valor.</small>';
  }
  function photo(r){return r.image?'<img src="'+escape(r.image)+'" loading="lazy" alt="Foto del anuncio">':'<div class="cmp-photo-empty">Sin foto</div>';}
  function precisionBadge(r){const p=presentation.precision(r);return '<span class="cmp-precision '+p.kind+'">'+escape(p.label)+'</span>';}
  function heading(r,selection){return '<div class="cmp-card-top">'+photo(r)+'<div class="cmp-card-main"><div class="cmp-card-sub">'+escape(r.source.toUpperCase())+' · '+escape(r.code)+' · '+Math.round(r.distance)+' m</div><div class="cmp-card-title">'+escape(r.title)+'</div><div class="cmp-card-price">'+money(r.price)+' <small>anunciado</small></div><div class="cmp-card-sub">'+escape(r.kind)+' · '+escape(r.district||'Sin distrito')+'</div>'+precisionBadge(r)+'</div>'+(selection&&!r.issues.length?'<label><input type="checkbox" data-include="'+escape(r.id)+'" '+(!excluded.has(r.id)?'checked':'')+' aria-label="Incluir '+escape(r.code)+'"> Incluir</label>':'')+'</div>';}
  function areas(r){return '<div class="cmp-card-areas"><span>Área de terreno<strong>'+decimals(r.land)+(r.land?' m²':'')+'</strong></span><span>Área construida<strong>'+decimals(r.built)+(r.built?' m²':'')+'</strong></span></div>';}
  function features(r){return r.kind==='Terreno'?'':'<p class="cmp-card-sub">Habitaciones: '+decimals(r.rooms)+' · Baños: '+decimals(r.baths)+(r.kind!=='Casa'?' · Piso: '+decimals(r.floor):'')+'</p>';}
  function breakdown(r){
    const v=value(r);
    if(v.status==='area')return '<section class="cmp-breakdown"><h3>'+escape(r.kind)+' · comparable por superficie construida</h3><div class="cmp-breakdown-grid"><div><span>Oferta por m² construido</span><strong>'+money(v.offerUnit)+'/m²</strong></div><div><span>Aplicada al área objetivo</span><strong>'+money(v.adjustedTotal)+'</strong></div></div><p class="cmp-equation">Se compara con inmuebles del mismo tipo; no se presenta como valor de suelo independiente.</p></section>';
    if(v.status==='land')return '<section class="cmp-breakdown"><h3>Terreno · referencia del suelo</h3><div class="cmp-breakdown-grid"><div><span>Oferta por m² de terreno</span><strong>'+money(v.offerUnit)+'/m²</strong></div><div><span>Uso en este análisis</span><small>'+(v.selected?'Incluido en la mediana del suelo':'Fuera del radio requerido; no participa')+'</small></div></div></section>';
    if(!['house','review'].includes(v.status))return '<p class="cmp-issues">'+escape(v.reason)+'</p>';
    return '<section class="cmp-breakdown '+(v.status==='review'?'review':'')+'"><h3>Valor atribuido por este anuncio</h3><div class="cmp-breakdown-grid"><div><span>Valor del terreno</span><strong>'+money(v.landValue)+'</strong><small>'+money(v.landUnit)+'/m² de suelo</small></div><div><span>Construcción y mejoras</span><strong>'+money(v.remainder)+'</strong><small>'+money(v.builtUnit)+'/m² construido</small></div></div><p class="cmp-equation">'+money(r.price)+' − ('+decimals(r.land)+' m² × '+money(v.landUnit)+'/m²) = '+money(v.remainder)+' en construcción y mejoras.</p>'+(v.reason?'<p class="cmp-issues">'+escape(v.reason)+'</p>':'')+'</section>';
  }
  function badge(r){const v=value(r);const text={area:'Incluida en el análisis',house:'Incluida en el análisis',review:'Requiere revisión',land:v.selected?'Terreno incluido':'Terreno de referencia',reference:'Solo referencia',excluded:'Desmarcada',pending:'Cálculo pendiente'};return '<span class="cmp-badge '+(['house','land','area'].includes(v.status)?'':'ref')+'">'+text[v.status]+'</span>';}
  function fixImages(container){container.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{const empty=document.createElement('div');empty.className='cmp-photo-empty';empty.textContent='Sin foto';img.replaceWith(empty);},{once:true}));}
  function renderCards(){
    const rows=visibleRows(),houses=rows.filter(r=>mapGroup(r)==='property'),lands=rows.filter(r=>mapGroup(r)==='land'),refs=rows.filter(r=>!['property','land'].includes(mapGroup(r)));
    $('cmp-house-count').textContent=houses.length;$('cmp-land-count').textContent=lands.length;$('cmp-ref-count').textContent=refs.length;
    const propertyType=snapshot.params.property_type,found=rows.filter(r=>r.kind===propertyType).length;
    $('cmp-counts').textContent=found+' '+propertyType.toLowerCase()+(found===1?' encontrada':'s encontradas')+' · '+houses.length+' comparables usados · '+lands.length+' terrenos usados · '+refs.length+' solo referencia';
    $('cmp-map-count').textContent=rows.length+' propiedades';
    document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
    const selected=tab==='reference'?refs:tab==='Casa'?houses:lands;
    $('cmp-cards').innerHTML=selected.map(r=>'<article class="cmp-card" data-record="'+escape(r.id)+'">'+heading(r,true)+areas(r)+features(r)+breakdown(r)+'<div class="cmp-card-footer">'+badge(r)+'<button type="button" data-detail="'+escape(r.id)+'">Ver detalle ↗</button></div></article>').join('')||'<p class="cmp-muted">No hay registros en este grupo.</p>';
    fixImages($('cmp-cards'));
  }
  function renderDetail(){
    if(!detailId||!snapshot)return;const r=snapshot.records.find(r=>r.id===detailId);if(!r)return;
    const recordFact=r.record_id?'<div>Registro interno<strong>#'+escape(r.record_id)+'</strong></div>':'';
    const editAction=r.record_id?'<button type="button" data-edit-record="'+escape(r.record_id)+'">Revisar / editar registro</button>':'';
    $('cmp-detail-content').innerHTML=heading(r,false)+areas(r)+features(r)+breakdown(r)+'<div class="cmp-detail-facts"><div>Código del portal<strong>'+escape(r.code||'Sin informar')+'</strong></div>'+recordFact+'<div>Ubicación<strong>'+escape(presentation.precision(r).label)+'</strong></div><div>Operación<strong>'+escape(r.operation)+'</strong></div><div>Disponibilidad<strong>'+escape(r.state)+'</strong></div><div>Distancia<strong>'+decimals(r.distance)+' m</strong></div><div>Precio<strong>'+(r.converted?'Convertido de soles a 3,44':'USD')+'</strong></div><div>Estado en ACM<strong>'+badge(r)+'</strong></div></div>'+(r.description?'<details><summary>Descripción del anuncio</summary><p class="cmp-description">'+escape(r.description)+'</p></details>':'')+'<p class="cmp-muted">En casas, construcción y mejoras es el remanente después de descontar el suelo estimado. En terrenos, departamentos y oficinas se muestra la referencia por la superficie correspondiente.</p><div class="cmp-card-footer">'+(r.url?'<a href="'+escape(r.url)+'" target="_blank" rel="noopener noreferrer">Abrir publicación ↗</a>':'<span>Sin enlace de publicación</span>')+editAction+'</div>';
    fixImages($('cmp-detail-content'));
  }
  function openDetail(id){detailId=id;renderDetail();if(!$('cmp-detail').open)$('cmp-detail').showModal();}
  function render(){renderSummary();renderCards();renderMap();renderDetail();$('cmp-export').disabled=false;}
  form.addEventListener('submit',async e=>{
    e.preventDefault();const p=input();if(!p.sources.length){$('cmp-status').textContent='Selecciona al menos una fuente.';return;}
    const seq=++sequence;snapshot=null;excluded.clear();if($('cmp-detail').open)$('cmp-detail').close();clearResult('Buscando comparables…');$('cmp-search').disabled=true;$('cmp-status').textContent='Buscando comparables del tipo seleccionado…';
    try{const data=await post('buscar',p);if(seq!==sequence)return;snapshot=data;result=data.result;tab=p.property_type==='Terreno'?'Terreno':'Casa';render();$('cmp-status').textContent='Análisis actualizado. Desmarca comparables para recalcular el mapa, las tarjetas y el resultado.';}
    catch(error){if(seq===sequence){snapshot=null;clearResult('La búsqueda no terminó. Reintenta.');$('cmp-status').textContent=error.message;}}
    finally{if(seq===sequence)$('cmp-search').disabled=false;}
  });
  form.addEventListener('input',e=>{if(e.target.name){if(e.target.name==='property_type')configureType();$('cmp-radius-label').textContent=form.elements.radius.value+' m';invalidate();}});
  form.addEventListener('change',e=>{if(e.target.name){if(e.target.name==='property_type')configureType();invalidate();}});
  $('cmp-address').addEventListener('keydown',e=>{if(e.key==='Enter')e.preventDefault();});
  document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{tab=button.dataset.tab;if(snapshot)renderCards();}));
  $('cmp-marker-mode').addEventListener('change',renderMap);
  document.querySelectorAll('[name=map_layer]').forEach(input=>input.addEventListener('change',renderMap));
  $('cmp-cards').addEventListener('click',e=>{const button=e.target.closest('[data-detail]');if(button)openDetail(button.dataset.detail);});
  $('cmp-detail-close').addEventListener('click',()=>$('cmp-detail').close());
  $('cmp-detail-content').addEventListener('click',e=>{const button=e.target.closest('[data-edit-record]');if(button&&typeof window.openScrapedEditor==='function')window.openScrapedEditor(button.dataset.editRecord);});
  $('cmp-detail').addEventListener('close',()=>{detailId=null;});
  $('cmp-detail').addEventListener('click',e=>{if(e.target===$('cmp-detail')){const b=e.target.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)e.target.close();}});
  $('cmp-cards').addEventListener('change',async e=>{
    const id=e.target.dataset.include;if(!id||!snapshot)return;e.target.checked?excluded.delete(id):excluded.add(id);const seq=++sequence;
    clearResult('Actualizando selección…');$('cmp-status').textContent='Recalculando suelo y construcción de cada casa…';
    try{const data=await post('calcular',{token:snapshot.token,excluded:[...excluded]});if(seq!==sequence)return;result=data.result;render();$('cmp-status').textContent='Mapa, propiedades y valoración actualizados con tu selección.';}
    catch(error){if(seq===sequence){clearResult('No se pudo aplicar la selección. Busca nuevamente.');$('cmp-status').textContent=error.message;}}
  });
  $('cmp-export').addEventListener('click',()=>{
    if(!snapshot||!result)return;const file={fecha:new Date().toISOString(),parametros:snapshot.params,advertencias:snapshot.warnings,excluidos:[...excluded],resultado:result,comparables:visibleRows().map(r=>({...r,analisis:value(r)}))};
    const url=URL.createObjectURL(new Blob([JSON.stringify(file,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='acm-componentes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  configureType();
})();
