(() => {
  'use strict';
  const $ = id => document.getElementById(id), form = $('cmp-form'), presentation = window.ACMComponentsPresentation;
  let snapshot=null, result=null, excluded=new Set(), tab='Casa', map=null, pin=null, circles=[], markers=[], sequence=0, controller=null, detailId=null;
  const money=n=>n==null?'—':new Intl.NumberFormat('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
  const decimals=n=>n==null?'Sin informar':new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(n);
  const formatDate=value=>{if(!value)return '—';const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString('es-PE',{dateStyle:'short',timeStyle:'short'});};
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
    // Mostrar toda la evidencia por defecto; las capas sirven para ocultar, no para perder registros.
    propertyLayer.checked=!land;landLayer.checked=house||land;propertyReferenceLayer.checked=house;otherReferenceLayer.checked=house||land;
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
    const urls={buscar:form.dataset.searchUrl,calcular:form.dataset.calculateUrl,guardar:form.dataset.saveUrl};
    try{const response=await fetch(urls[path],{method:'POST',credentials:'same-origin',signal:current.signal,headers:{'Content-Type':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value},body:JSON.stringify(data)});
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
    result=null;clearMap();drawCircles();$('cmp-export').disabled=true;$('cmp-word').disabled=true;$('cmp-save').disabled=true;$('cmp-save').textContent='Guardar en historial';
    $('cmp-new').innerHTML='<h2>Valoración por componentes</h2><p class="cmp-muted">'+escape(message)+'</p>';
    $('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>—</strong>';
    $('cmp-map-count').textContent='Sin análisis vigente';
    $('cmp-calculation-explanation').innerHTML='<p class="cmp-muted">Busca comparables para ver aquí las operaciones con sus valores reales.</p>';
    if(snapshot){renderCards();renderDetail();}else{$('cmp-cards').innerHTML='<p class="cmp-muted">Busca comparables para aplicar el análisis.</p>';$('cmp-counts').textContent='Sin comparables';['house','land','ref'].forEach(k=>$('cmp-'+k+'-count').textContent='');}
  }
  function invalidate(){
    sequence++;if(controller)controller.abort();snapshot=null;excluded.clear();if($('cmp-detail').open)$('cmp-detail').close();
    clearResult('Parámetros modificados: vuelve a buscar.');$('cmp-warnings').replaceChildren();$('cmp-status').textContent='Listo para una nueva búsqueda.';$('cmp-search').disabled=false;
  }
  function setLocation(lat,lng){form.elements.lat.value=lat.toFixed(7);form.elements.lng.value=lng.toFixed(7);invalidate();if(map)map.panTo({lat,lng});}
  function hideGoogleGestureHint(){
    const host=$('cmp-map'),phrases=['utiliza la tecla ctrl','usa la tecla ctrl','use ctrl','hold ctrl','mantén pulsada la tecla ctrl'];
    host.querySelectorAll('.gm-style-pbc,[class*="gm-style-pbc"],div,span').forEach(node=>{
      const ownText=Array.from(node.childNodes).filter(child=>child.nodeType===Node.TEXT_NODE).map(child=>child.textContent).join(' ').trim().toLocaleLowerCase();
      const keyboardHint=ownText.includes('ctrl')&&(ownText.includes('rueda')||ownText.includes('scroll')||ownText.includes('desplaz'));
      if(node.classList?.contains('gm-style-pbc')||keyboardHint||phrases.some(phrase=>ownText.includes(phrase))){
        const overlay=node.closest('.gm-style-pbc,[class*="gm-style-pbc"]')||node;
        overlay.style.setProperty('display','none','important');
        overlay.setAttribute('aria-hidden','true');
      }
    });
  }
  window.initComponentMap=()=>{
    const p=input();map=new google.maps.Map($('cmp-map'),{center:{lat:p.lat,lng:p.lng},zoom:15,mapTypeControl:false,streetViewControl:false,gestureHandling:'greedy'});map.addListener('click',e=>setLocation(e.latLng.lat(),e.latLng.lng()));
    const auto=new google.maps.places.Autocomplete($('cmp-address'),{fields:['geometry','formatted_address'],componentRestrictions:{country:'pe'}});
    auto.addListener('place_changed',()=>{const place=auto.getPlace();if(place.geometry){setLocation(place.geometry.location.lat(),place.geometry.location.lng());map.setZoom(16);}});
    const gestureObserver=new MutationObserver(hideGoogleGestureHint);gestureObserver.observe($('cmp-map'),{childList:true,subtree:true,characterData:true});hideGoogleGestureHint();
    drawCircles();if(snapshot&&result)renderMap();
  };
  window.gm_authFailure=()=>{$('cmp-status').textContent='No se pudo cargar Google Maps. Puedes ingresar latitud y longitud para buscar.';};
  // Keep all consulted records visible so an excluded outer land can be selected again.
  function visibleRows(){return snapshot?.records||[];}
  const value=r=>presentation.property(r,result,excluded);
  const mapGroup=r=>presentation.group(r,value(r));
  function similarityOrder(rows){return [...rows].sort((a,b)=>{
    const av=value(a),bv=value(b);
    const aWeight=av.similarityWeight==null?(a.overall_similarity==null?-1:a.overall_similarity):av.similarityWeight;
    const bWeight=bv.similarityWeight==null?(b.overall_similarity==null?-1:b.overall_similarity):bv.similarityWeight;
    if (bWeight!==aWeight) return bWeight-aWeight;
    return (a.distance||0)-(b.distance||0) || String(a.id).localeCompare(String(b.id));
  });}
  function visibleMapRows(){const layers=new Set(Array.from(document.querySelectorAll('[name=map_layer]:checked'),x=>x.value));return visibleRows().filter(r=>layers.has(mapGroup(r)));}
  function renderMap(){
    if(!map||!result)return;clearMap();drawCircles();
    const icons={propify:'Pin-propify.png',remax:'pin-remax.png',properati:'pin-properati.png'};
    const mode=$('cmp-marker-mode').value;
    const rows=visibleMapRows();
    rows.forEach(r=>{
      const v=value(r),label=presentation.marker(r,v,mode),dim=['reference','excluded','pending'].includes(v.status);
      const icon=icons[r.source]?{url:'/static/requerimientos/data/'+icons[r.source],scaledSize:new google.maps.Size(32,40),anchor:new google.maps.Point(16,40),labelOrigin:new google.maps.Point(16,52)}:{path:google.maps.SymbolPath.CIRCLE,scale:7,fillColor:r.kind==='Terreno'?'#d6a548':'#3789dd',fillOpacity:1,strokeColor:'#ffffff',strokeWeight:1,labelOrigin:new google.maps.Point(0,3)};
      const marker=new google.maps.Marker({map,position:{lat:r.lat,lng:r.lng},title:r.title+' · '+presentation.precision(r).label+' · '+label,opacity:dim?.55:1,zIndex:1000+Math.round((r.overall_similarity||0)*10),icon,label:{text:label,fontSize:'10px',fontWeight:'600',className:'cmp-pin-label'}});
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
  function medianExplanation(values){
    const ordered=[...values].sort((a,b)=>a-b),formatted=ordered.map(v=>money(v)+'/m²').join(', ');
    if(!ordered.length)return 'No hubo valores aptos.';
    if(ordered.length%2)return 'Ordenados: '+formatted+'. El valor central es '+money(ordered[Math.floor(ordered.length/2)])+'/m².';
    const left=ordered[ordered.length/2-1],right=ordered[ordered.length/2];
    return 'Ordenados: '+formatted+'. Se promedian los dos centrales: ('+money(left)+' + '+money(right)+') ÷ 2 = '+money((left+right)/2)+'/m².';
  }
  function calculationTable(headers,rows){return '<div class="cmp-calc-scroll"><table class="cmp-calc-table"><thead><tr>'+headers.map(h=>'<th>'+escape(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(value=>'<td>'+value+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
  function renderCalculationExplanation(){
    const host=$('cmp-calculation-explanation'),r=result,p=snapshot.params;
    if(r.model!=='components'){
      const basis=r.model==='land'?'terreno':'área construida',rows=r.breakdown.map(detail=>{const record=visibleRows().find(row=>row.id===detail.id);return [escape(record?.source?.toUpperCase()||''),escape(record?.code||detail.id),money(detail.price||record?.price),decimals(detail.area)+' m²',money(detail.offer_unit)+'/m²'];});
      host.innerHTML='<h3>1. Convertimos cada anuncio a una misma unidad</h3><p>Precio anunciado ÷ '+basis+' = precio por m².</p>'+calculationTable(['Portal','Código','Precio','Área','Precio por m²'],rows)+'<h3>2. Tomamos el valor central</h3><p>'+escape(medianExplanation(r.breakdown.map(detail=>detail.offer_unit)))+'</p>'+(r.new?'<h3>3. Aplicamos el valor al inmueble objetivo</h3><p>'+decimals(p[r.new.area_basis])+' m² × '+money(r.new.unit)+'/m² = <strong>'+money(r.new.total)+'</strong>.</p>':'<p>No hubo comparables aptos para completar el cálculo.</p>');return;
    }
    const lands=r.land_ids.map(id=>visibleRows().find(row=>row.id===id)).filter(Boolean),landUnits=lands.map(row=>row.price/row.land);
    const details=r.breakdown.map(detail=>({detail,record:visibleRows().find(row=>row.id===detail.id)})).filter(item=>item.record),usable=details.filter(item=>item.detail.usable);
    let html='<h3>1. Calculamos el suelo con '+lands.length+' terreno(s)</h3><p>Cada terreno se convierte a precio por m²: precio anunciado ÷ área del terreno.</p>';
    if(lands.length)html+=calculationTable(['Portal','Código','Operación'],lands.map(row=>[escape(row.source.toUpperCase()),escape(row.code),money(row.price)+' ÷ '+decimals(row.land)+' m² = <strong>'+money(row.price/row.land)+'/m²</strong>']))+'<p>'+escape(medianExplanation(landUnits))+' Se adopta <strong>'+money(r.land_unit)+'/m²</strong> para el suelo.</p>';
    else html+='<p>No hubo terrenos aptos; el proceso no puede separar suelo y construcción.</p>';
    html+='<h3>2. Separamos suelo y construcción en cada casa</h3><p>Precio de la casa − (área de terreno × valor del suelo) = remanente. Luego: remanente ÷ área construida = aporte por m² construido.</p>';
    if(details.length)html+=calculationTable(['Casa','Cálculo del remanente','Sim. terreno','Sim. construcción','Aporte por m²','Valor sugerido para el objetivo'],details.map(({record,detail})=>[escape(record.source.toUpperCase()+' · '+record.code),money(record.price)+' − ('+decimals(record.land)+' × '+money(r.land_unit)+') = '+money(detail.remainder),decimals(detail.land_similarity)+'%',decimals(detail.built_similarity)+'%',money(detail.built_unit)+'/m²',detail.usable?money(detail.target_estimate):'No participa · solo referencia']));
    if(usable.length){
      const selected=usable.find(item=>item.detail.id===r.built_reference_id);
      html+='<p>'+(r.built_unit_method==='closest_comparable'&&selected
        ?'Solo hay dos casas y sus aportes están muy dispersos. Se usa el comparable más parecido a las superficies y la ubicación: <strong>'+escape(selected.record.source.toUpperCase()+' · '+selected.record.code)+'</strong>, con '+money(selected.detail.built_unit)+'/m². La otra casa permanece como referencia y no se promedian los extremos.'
        :r.built_unit_method==='weighted_median'
        ?'Los aportes están muy dispersos. Se usa una mediana ponderada por similitud: las casas con terreno, construcción y ubicación más parecidos tienen mayor peso.'
        :escape(medianExplanation(usable.map(item=>item.detail.built_unit))+' Este valor central es el aporte unitario aplicado al objetivo.'))+'</p>';
    }
    html+='<h3>3. Aplicamos ambos componentes al inmueble objetivo</h3>';
    if(r.new)html+='<p>Suelo: '+decimals(p.land)+' m² × '+money(r.land_unit)+'/m² = <strong>'+money(r.new.land_value)+'</strong>.</p><p>Construcción y mejoras: '+decimals(p.built)+' m² × '+money(r.new.built_unit)+'/m² = <strong>'+money(r.new.built_value)+'</strong>.</p><p>Resultado: '+money(r.new.land_value)+' + '+money(r.new.built_value)+' = <strong>'+money(r.new.total)+'</strong>.</p><p>Las casas usadas sugieren valores individuales entre <strong>'+money(r.new.range_low)+'</strong> y <strong>'+money(r.new.range_high)+'</strong> para el inmueble objetivo.</p>';
    else html+='<p>No se completó este paso porque faltó un componente válido.</p>';
    host.innerHTML=html;
  }
  function photo(r){return r.image?'<img src="'+escape(r.image)+'" loading="lazy" alt="Foto del anuncio">':'<div class="cmp-photo-empty">Sin foto</div>';}
  function precisionBadge(r){const p=presentation.precision(r);return '<span class="cmp-precision '+p.kind+'">'+escape(p.label)+'</span>';}
  function publicationBadge(r){const labels={activa:'Activa',posible_retirada:'Posible retirada',retirada:'Retirada',sin_verificar:'Sin verificar'};const state=labels[r.state]||'Sin verificar';const misses=r.consecutive_absences?' · '+r.consecutive_absences+' ausencia(s)':'';return '<span class="cmp-publication-state state-'+escape(r.state||'sin_verificar')+'">Publicación: '+escape(state+misses)+'</span>';}
  function similarityBlock(r){const overall=r.overall_similarity;if(overall==null)return '';const v=value(r);const weight=v.similarityWeight==null?'':'<span>Peso en cálculo '+decimals(v.similarityWeight)+'%</span>';return '<div class="cmp-similarity cmp-similarity-visible"><strong>Similitud con tu inmueble: '+decimals(overall)+'%</strong><span>Terreno '+decimals(r.land_similarity)+'%</span><span>Construcción '+decimals(r.built_similarity)+'%</span><span>Distancia '+decimals(r.distance_similarity)+'%</span>'+weight+'</div>';}
  function heading(r,selection){return '<div class="cmp-card-top">'+photo(r)+'<div class="cmp-card-main"><div class="cmp-card-sub">'+escape(r.source.toUpperCase())+' · '+escape(r.code)+' · '+Math.round(r.distance)+' m</div><div class="cmp-card-title">'+escape(r.title)+'</div><div class="cmp-card-price">'+money(r.price)+' <small>anunciado</small></div><div class="cmp-card-sub">'+escape(r.kind)+' · '+escape(r.district||'Sin distrito')+'</div>'+precisionBadge(r)+' '+publicationBadge(r)+similarityBlock(r)+'</div>'+(selection&&!r.issues.length?'<label><input type="checkbox" data-include="'+escape(r.id)+'" '+(!excluded.has(r.id)?'checked':'')+' aria-label="Incluir '+escape(r.code)+'"> Incluir</label>':'')+'</div>';}
  function areas(r){return '<div class="cmp-card-areas"><span>Área de terreno<strong>'+decimals(r.land)+(r.land?' m²':'')+'</strong></span><span>Área construida<strong>'+decimals(r.built)+(r.built?' m²':'')+'</strong></span></div>';}
  function features(r){return r.kind==='Terreno'?'':'<p class="cmp-card-sub">Habitaciones: '+decimals(r.rooms)+' · Baños: '+decimals(r.baths)+(r.kind!=='Casa'?' · Piso: '+decimals(r.floor):'')+'</p>';}
  function breakdown(r){
    const v=value(r);
    if(v.status==='area')return '<section class="cmp-breakdown"><h3>'+escape(r.kind)+' · comparable por superficie construida</h3><div class="cmp-breakdown-grid"><div><span>Oferta por m² construido</span><strong>'+money(v.offerUnit)+'/m²</strong></div><div><span>Aplicada al área objetivo</span><strong>'+money(v.adjustedTotal)+'</strong></div></div><p class="cmp-equation">Se compara con inmuebles del mismo tipo; no se presenta como valor de suelo independiente.</p></section>';
    if(v.status==='land')return '<section class="cmp-breakdown"><h3>Terreno · referencia del suelo</h3><div class="cmp-breakdown-grid"><div><span>Oferta por m² de terreno</span><strong>'+money(v.offerUnit)+'/m²</strong></div><div><span>Uso en este análisis</span><small>'+(v.selected?'Incluido en la mediana del suelo':'Fuera del radio requerido; no participa')+'</small></div></div></section>';
    if(!['house','review'].includes(v.status))return '<p class="cmp-issues">'+escape(v.reason)+'</p>';
    return '<section class="cmp-breakdown '+(v.status==='review'?'review':'')+'"><h3>Valor atribuido por este anuncio '+(v.recommended?'<span class="cmp-recommended">Recomendada · '+decimals(v.similarityWeight)+'% de peso</span>':'')+'</h3><div class="cmp-breakdown-grid"><div><span>Valor del terreno</span><strong>'+money(v.landValue)+'</strong><small>'+money(v.landUnit)+'/m² de suelo</small></div><div><span>Construcción y mejoras</span><strong>'+money(v.remainder)+'</strong><small>'+money(v.builtUnit)+'/m² construido</small></div><div><span>Valor que sugiere para el inmueble objetivo</span><strong>'+(v.status==='review'?'No participa':money(v.targetEstimate))+'</strong><small>'+(v.status==='review'?'Remanente no positivo · solo referencia':decimals(snapshot.params.land)+' m² terreno + '+decimals(snapshot.params.built)+' m² construidos')+'</small></div></div><div class="cmp-similarity"><span>Similitud con el objetivo</span><span>Terreno <strong>'+decimals(v.landSimilarity)+'%</strong></span><span>Construcción <strong>'+decimals(v.builtSimilarity)+'%</strong></span><span>Distancia <strong>'+decimals(v.distanceSimilarity)+'%</strong></span><span>Total <strong>'+decimals(v.overallSimilarity)+'%</strong></span><span>Peso relativo <strong>'+decimals(v.similarityWeight)+'%</strong></span></div><p class="cmp-equation">'+money(r.price)+' − ('+decimals(r.land)+' m² × '+money(v.landUnit)+'/m²) = '+money(v.remainder)+' en construcción y mejoras.</p>'+(v.reason?'<p class="cmp-issues">'+escape(v.reason)+'</p>':'')+'</section>';
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
    $('cmp-cards').innerHTML=similarityOrder(selected).map(r=>'<article class="cmp-card" data-record="'+escape(r.id)+'">'+heading(r,true)+areas(r)+features(r)+breakdown(r)+'<div class="cmp-card-footer">'+badge(r)+'<button type="button" data-detail="'+escape(r.id)+'">Ver detalle ↗</button></div></article>').join('')||'<p class="cmp-muted">No hay registros en este grupo.</p>';
    fixImages($('cmp-cards'));
  }
  function renderDetail(){
    if(!detailId||!snapshot)return;const r=snapshot.records.find(r=>r.id===detailId);if(!r)return;
    const recordFact=r.record_id?'<div>Registro interno<strong>#'+escape(r.record_id)+'</strong></div>':'';
    const editAction=r.record_id?'<button type="button" data-edit-record="'+escape(r.record_id)+'">Revisar / editar registro</button>':'';
    const lifecycle='<div>Primera vez vista<strong>'+escape(formatDate(r.first_seen))+'</strong></div><div>Última vez vista<strong>'+escape(formatDate(r.last_seen))+'</strong></div><div>Primera ausencia<strong>'+escape(formatDate(r.first_missing))+'</strong></div><div>Retiro confirmado<strong>'+escape(formatDate(r.retired_at))+'</strong></div>';
    $('cmp-detail-content').innerHTML=heading(r,false)+similarityBlock(r)+areas(r)+features(r)+breakdown(r)+'<div class="cmp-detail-facts"><div>Código del portal<strong>'+escape(r.code||'Sin informar')+'</strong></div>'+recordFact+'<div>Ubicación<strong>'+escape(presentation.precision(r).label)+'</strong></div><div>Operación<strong>'+escape(r.operation)+'</strong></div><div>Disponibilidad<strong>'+publicationBadge(r)+'</strong></div>'+lifecycle+'<div>Distancia<strong>'+decimals(r.distance)+' m</strong></div><div>Precio<strong>'+(r.converted?'Convertido de soles a 3,44':'USD')+'</strong></div><div>Estado en ACM<strong>'+badge(r)+'</strong></div></div>'+(r.description?'<details><summary>Descripción del anuncio</summary><p class="cmp-description">'+escape(r.description)+'</p></details>':'')+'<p class="cmp-muted">En casas, construcción y mejoras, el remanente se calcula después de descontar el suelo estimado. Una publicación retirada permanece visible como referencia y no participa en el cálculo.</p><div class="cmp-card-footer">'+(r.url?'<a href="'+escape(r.url)+'" target="_blank" rel="noopener noreferrer">Abrir publicación ↗</a>':'<span>Sin enlace de publicación</span>')+editAction+'</div>';
    fixImages($('cmp-detail-content'));
  }
  function openDetail(id){detailId=id;renderDetail();if(!$('cmp-detail').open)$('cmp-detail').showModal();}
  function render(){renderSummary();renderCalculationExplanation();renderCards();renderMap();renderDetail();$('cmp-export').disabled=false;$('cmp-word').disabled=!result.new;$('cmp-save').disabled=!result.new;}
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
  $('cmp-save').addEventListener('click',async()=>{
    if(!snapshot||!result||!result.new)return;const button=$('cmp-save');button.disabled=true;$('cmp-status').textContent='Guardando análisis y selección en el historial…';
    try{const data=await post('guardar',{token:snapshot.token,excluded:[...excluded]});button.textContent='Guardado · '+data.code;$('cmp-status').textContent=data.created?'Análisis guardado en el historial.':'Este mismo análisis ya estaba guardado en el historial.';}
    catch(error){$('cmp-status').textContent=error.message;button.disabled=false;}
  });
  $('cmp-word').addEventListener('click',async()=>{
    if(!snapshot||!result)return;const button=$('cmp-word');button.disabled=true;$('cmp-status').textContent='Generando informe Word con las operaciones del análisis…';
    try{const response=await fetch(form.dataset.reportUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value},body:JSON.stringify({token:snapshot.token,excluded:[...excluded]})});
      if(!response.ok){let body={};try{body=await response.json();}catch(e){}throw Error(body.error||'No se pudo generar el informe Word.');}
      const code=response.headers.get('X-ACM-History-Code')||'';const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=(code||'informe-acm')+'.docx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('cmp-save').textContent=code?'Guardado · '+code:'Guardado en historial';$('cmp-save').disabled=true;$('cmp-status').textContent='Informe Word descargado y análisis guardado en el historial.';
    }catch(error){$('cmp-status').textContent=error.message;}finally{button.disabled=false;}
  });
  configureType();
})();
