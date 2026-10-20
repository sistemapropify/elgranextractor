(() => {
  'use strict';
  const $ = id => document.getElementById(id), form = $('cmp-form'), presentation = window.ACMComponentsPresentation;
  const permissions=window.ACMPermissions||{};
  let snapshot=null, result=null, excluded=new Set(), tab='Casa', map=null, pin=null, circles=[], markers=[], sequence=0, controller=null, detailId=null, selectedMapId=null;
  let aiController=null, aiExplanation=null, aiProposal=null;
  let reportDownloading=false, restoredViewport=null;
  let locationLocked=false, searching=false;
  const locatedIds=new Set();
  const unselected=new Set();
  let pulseMarkers=[],pulseTimer=null;
  const money=(n,digits=0)=>n==null?'—':new Intl.NumberFormat('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:digits}).format(n);
  const decimals=n=>n==null?'Sin informar':new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(n);
  const age=n=>n==null||!Number.isFinite(Number(n))||Number(n)<0?'Sin informar':Number(n)===0?'Estreno':decimals(n)+(Number(n)===1?' año':' años');
  const formatDate=value=>{if(!value)return '—';const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString('es-PE',{dateStyle:'short',timeStyle:'short'});};
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function input(){return {property_type:form.elements.property_type.value,age:form.elements.age.disabled?null:form.elements.age.value,address:$('cmp-address').value,rooms:form.elements.rooms.disabled?null:form.elements.rooms.value,baths:form.elements.baths.disabled?null:form.elements.baths.value,floor:form.elements.floor.disabled?null:form.elements.floor.value,lat:Number(form.elements.lat.value),lng:Number(form.elements.lng.value),land:Number(form.elements.land.value),built:Number(form.elements.built.value),radius:Number(form.elements.radius.value),max_radius:Number(form.elements.max_radius.value),sources:Array.from(form.querySelectorAll('[name=source]:not(:disabled)'),x=>x.value)};}
  function requestLogin(){
    $('cmp-status').textContent='Inicia sesión para consultar la zonificación y calcular comparables.';
    window.location.assign('/acm/login/?next='+encodeURIComponent(window.location.pathname));
    const modal=$('login-modal');
    if(modal)modal.style.display='flex';
  }
  function setLocationLocked(locked){locationLocked=locked;if(pin)pin.setDraggable(!locked);}
  function setSearchFormCollapsed(collapsed){
    form.hidden=collapsed;const toggle=$('cmp-form-toggle');toggle.disabled=searching;
    toggle.setAttribute('aria-expanded',String(!collapsed));
    toggle.innerHTML=(searching?'Buscando comparables…':collapsed?'Buscar y calcular':'Parámetros de búsqueda')+' <span aria-hidden="true">'+(collapsed?'+':'−')+'</span>';
    $('cmp-search-actions').hidden=!collapsed||searching;
    $('cmp-move-pin').disabled=searching;$('cmp-new-acm').disabled=searching;
  }
  function reopenSearch(){
    if(searching)return;
    setSearchFormCollapsed(false);
    if(locationLocked){setLocationLocked(false);invalidate();}
    $('cmp-search-message').hidden=true;
    $('cmp-status').textContent='Mueve el pin o modifica los datos y vuelve a pulsar Buscar y calcular.';
  }
  function configureType(){
    const type=form.elements.property_type.value,house=type==='Casa',oldHouse=house&&form.elements.age.value!==''&&Number(form.elements.age.value)>=30,land=type==='Terreno',hideBuilt=land||oldHouse,soil=hideBuilt||(house&&(form.elements.built.value.trim()===''||Number(form.elements.built.value)===0));
    [['land',house||land],['built',!hideBuilt],['age',!land],['rooms',house||type==='Departamento'],['baths',!land],['floor',!house&&!land]].forEach(([key,show])=>{
      $('cmp-'+key+'-field').hidden=!show;form.elements[key].disabled=!show;
      if(key==='land'||key==='built')form.elements[key].required=show&&(key!=='built'||!house);
    });
    form.elements.built.min=house?'0':'0.01';
    document.querySelector('label[for="cmp-built"]').textContent=house?'Construcción (m², opcional)':'Construcción (m²)';
    const methodLabel=$('cmp-method-label');
    if(methodLabel)methodLabel.textContent=oldHouse?'Casa de 30 años o más: valoración únicamente del terreno':house?(soil?'Casa sin área construida: valoración únicamente del terreno':'Casa: suelo + construcción y mejoras'):land?'Terreno: comparables de suelo':'Comparables de '+type.toLowerCase()+' por superficie construida';
    document.querySelector('[data-tab="Casa"]').hidden=soil;
    document.querySelector('[data-tab="Terreno"]').hidden=!house&&!land;
    const mode=$('cmp-marker-mode');if(mode.options){mode.options[0].textContent=house||land?'Suelo / m²':'Oferta / m² construido';mode.options[1].disabled=!house;}if(!house&&mode.value==='improvements')mode.value='land';
    const propertyLayer=document.querySelector('[name=map_layer][value=property]'),landLayer=document.querySelector('[name=map_layer][value=land]'),propertyReferenceLayer=document.querySelector('[name=map_layer][value=property_reference]'),otherReferenceLayer=document.querySelector('[name=map_layer][value=other_reference]');
    // Al cambiar el tipo, empezar con una sola capa: los comparables del inmueble analizado.
    propertyLayer.checked=!soil;landLayer.checked=soil;propertyReferenceLayer.checked=false;otherReferenceLayer.checked=false;
    propertyLayer.closest('label').hidden=soil;propertyReferenceLayer.closest('label').hidden=land;
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
      if(response.status===401)requestLogin();
      if(!response.headers.get('content-type')?.includes('application/json'))throw Error('El servidor no devolvió datos. Comprueba tu sesión y vuelve a intentar.');
      const body=await response.json();if(!response.ok)throw Error(body.error||'No se pudo completar la consulta.');return body;
    }catch(e){if(e.name==='AbortError')throw Error('La consulta se canceló o superó 45 segundos. Puedes reintentar.');throw e;}finally{clearTimeout(timer);}
  }
  function clearMap(){
    clearInterval(pulseTimer);pulseTimer=null;
    pulseMarkers.forEach(m=>m.setMap(null));pulseMarkers=[];
    markers.forEach(m=>m.setMap(null));markers=[];
  }
  function pulseIcon(phase){return {path:google.maps.SymbolPath.CIRCLE,scale:15+phase*17,fillColor:'#00e5ff',fillOpacity:.18*(1-phase),strokeColor:'#00e5ff',strokeOpacity:1-phase*.8,strokeWeight:3};}
  function startMapPulses(){
    if(!pulseMarkers.length||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    const started=Date.now();
    pulseTimer=setInterval(()=>{
      if(document.hidden)return;
      const icon=pulseIcon(((Date.now()-started)%1400)/1400);
      pulseMarkers.forEach(marker=>marker.setIcon(icon));
    },80);
  }
  function locateProperty(id){
    const row=visibleRows().find(r=>String(r.id)===id);
    if(!row)return;
    if(!map||!result){$('cmp-status').textContent='Espera a que el mapa y el análisis estén disponibles.';return;}
    if(!presentation.inMapRadius(row,snapshot.params,result,mapGroup(row))){$('cmp-status').textContent='Esta referencia está a '+decimals(row.distance)+' m, fuera del radio de '+decimals(snapshot.params.radius)+' m del mapa.';return;}
    const active=!locatedIds.has(id);
    if(active){
      locatedIds.add(id);
      const layer=Array.from(document.querySelectorAll('[name=map_layer]')).find(el=>el.value===mapGroup(row));
      if(layer)layer.checked=true;
    }else locatedIds.delete(id);
    renderMap();renderComparison();
    document.querySelectorAll('[data-locate]').forEach(button=>{
      const selected=locatedIds.has(button.dataset.locate);
      button.setAttribute('aria-pressed',String(selected));
      button.textContent=selected?'Dejar de palpitar en el mapa':'Buscar propiedad en el mapa';
    });
    if(active){
      map.panTo({lat:row.lat,lng:row.lng});
      $('cmp-map').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'});
    }
  }
  function drawCircles(){
    if(!map)return;circles.forEach(c=>c.setMap(null));circles=[];
    const p=snapshot?.params||input(),center={lat:p.lat,lng:p.lng};if(!Number.isFinite(center.lat)||!Number.isFinite(center.lng))return;
    if(!pin)pin=new google.maps.Marker({map,position:center,title:'Inmueble objetivo',draggable:!locationLocked});else{pin.setPosition(center);pin.setDraggable(!locationLocked);}
    if(!pin.cmpListener){pin.addListener('dragend',e=>setLocation(e.latLng.lat(),e.latLng.lng()));pin.addListener('click',()=>{const p=pin.getPosition();document.dispatchEvent(new CustomEvent('acm:target-location',{detail:{lat:p.lat(),lng:p.lng()}}));});pin.cmpListener=true;}
    const layers=new Set(Array.from(document.querySelectorAll('[name=map_layer]:checked'),el=>el.value));
    const rings=presentation.mapRings(p,result,layers);
    rings.forEach((ring,index)=>{
      // El contorno debe quedar sobre la zonificación (zIndex 100000),
      // sin tapar sus colores ni interceptar los clics para elegir ubicación.
      const options={map,center,radius:ring.radius,fillOpacity:0,clickable:false};
      circles.push(new google.maps.Circle({...options,strokeColor:'#ffffff',strokeWeight:6,strokeOpacity:.9,zIndex:1000000+index*2}));
      circles.push(new google.maps.Circle({...options,strokeColor:ring.color,strokeWeight:3,strokeOpacity:1,zIndex:1000001+index*2}));
    });
    $('cmp-radius-note').innerHTML=rings.map(ring=>'<span><i style="background:'+ring.color+'" aria-hidden="true"></i>'+escape(ring.label)+': '+decimals(ring.radius)+' m</span>').join('');
  }
  function fitSearchRadius(){if(map&&circles.length)map.fitBounds(circles[0].getBounds(),{top:40,right:24,bottom:32,left:Math.min($('cmp-controls').offsetWidth+24,Math.round($('map-container').clientWidth*.35))});}
  function clearResult(message){
    reportStatus('');
    if(aiController)aiController.abort();aiController=null;aiExplanation=null;
    $('cmp-ai-panel').hidden=true;$('cmp-ai-status').textContent='';
    aiProposal=null;$('cmp-proposal').hidden=true;
    $('cmp-simple').textContent='';
    $('cmp-scenario').hidden=true;
    result=null;clearMap();drawCircles();$('cmp-export').disabled=true;$('cmp-word').disabled=true;$('cmp-pdf').disabled=true;$('cmp-save').disabled=true;$('cmp-save').textContent='Guardar en historial';
    $('cmp-new').innerHTML='<h2>Valoración por componentes</h2><p class="cmp-muted">'+escape(message)+'</p>';
    $('cmp-map-count').textContent='Sin análisis vigente';
    $('cmp-calculation-explanation').innerHTML='<p class="cmp-muted">Busca comparables para ver aquí las operaciones con sus valores reales.</p>';
    $('cmp-calculation-open').disabled=true;
    $('cmp-comparison').hidden=true;
    $('cmp-comparison-report').disabled=true;
    $('cmp-html').disabled=true;
    setReportMenu(false);
    $('cmp-comparison-open').hidden=true;
    $('cmp-comparison-content').replaceChildren();
    clearSelectedRecord();
    window.ACMComparisonValuation?.reset();
    $('cmp-warnings').replaceChildren();$('cmp-notices').hidden=true;
    if($('cmp-calculation').open)$('cmp-calculation').close();
    if(snapshot){renderCards();renderDetail();}else{$('cmp-cards').innerHTML='<p class="cmp-muted">Busca comparables para aplicar el análisis.</p>';$('cmp-counts').textContent='Sin comparables';['house','land','ref'].forEach(k=>$('cmp-'+k+'-count').textContent='');}
  }
  function invalidate(){
    sequence++;if(controller)controller.abort();snapshot=null;excluded.clear();unselected.clear();locatedIds.clear();if($('cmp-detail').open)$('cmp-detail').close();
    clearSelectedRecord();
    clearResult('Parámetros modificados: vuelve a buscar.');$('cmp-warnings').replaceChildren();$('cmp-status').textContent='Listo para una nueva búsqueda.';$('cmp-search').disabled=false;
  }
  function setLocation(lat,lng){if(locationLocked)return;form.elements.lat.value=lat.toFixed(7);form.elements.lng.value=lng.toFixed(7);invalidate();if(map)map.panTo({lat,lng});if(window.ACMZona)window.ACMZona.actualizar(lat,lng);document.dispatchEvent(new CustomEvent('acm:target-location',{detail:{lat,lng}}));}
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
    const p=input();map=new google.maps.Map($('cmp-map'),{center:restoredViewport?{lat:restoredViewport.lat,lng:restoredViewport.lng}:{lat:p.lat,lng:p.lng},zoom:restoredViewport?.zoom??15,mapTypeControl:false,streetViewControl:!!permissions.street_view,gestureHandling:'greedy'});map.addListener('click',e=>setLocation(e.latLng.lat(),e.latLng.lng()));
    const auto=new google.maps.places.Autocomplete($('cmp-address'),{fields:['geometry','formatted_address'],componentRestrictions:{country:'pe'}});
    auto.addListener('place_changed',()=>{const place=auto.getPlace();if(place.geometry){setLocation(place.geometry.location.lat(),place.geometry.location.lng());map.setZoom(16);}});
    const gestureObserver=new MutationObserver(hideGoogleGestureHint);gestureObserver.observe($('cmp-map'),{childList:true,subtree:true,characterData:true});hideGoogleGestureHint();
    drawCircles();if(snapshot&&result)renderMap();
    if(permissions.pdm_polygons&&window.CapasMapa)window.CapasMapa.init(map,{configUrl:'/acm/capas-mapa/'});
    if(window.ACMNearby)window.ACMNearby.init(map);
    if(permissions.cadastral_info&&window.ACMCadastral)window.ACMCadastral.init(map);
  };
  window.gm_authFailure=()=>{$('cmp-status').textContent='No se pudo cargar Google Maps. Puedes ingresar latitud y longitud para buscar.';};
  // Keep all consulted records visible so an excluded outer land can be selected again.
  function visibleRows(){const records=snapshot?.records||[];return result?.reference_mode?records.filter(row=>result.reference_display_ids.includes(row.id)||result.land_ids.includes(row.id)):records;}
  const value=r=>presentation.property(r,result,excluded);
  const mapGroup=r=>presentation.group(r,value(r));
  const comparableRows=()=>visibleRows().filter(r=>mapGroup(r)==='property');
  function similarityOrder(rows){return [...rows].sort((a,b)=>{
    if(['nearest','nearest_group'].includes(result?.selection_method))return (a.distance||0)-(b.distance||0)||(b.surface_similarity||0)-(a.surface_similarity||0)||String(a.id).localeCompare(String(b.id));
    if(result?.selection_method==='age_proximity')return (snapshot.params.age===0?Number(b.age===0)-Number(a.age===0):0)||(b.selection_score||0)-(a.selection_score||0)||(a.distance||0)-(b.distance||0)||String(a.id).localeCompare(String(b.id));
    const av=value(a),bv=value(b);
    const aWeight=av.similarityWeight==null?(a.overall_similarity==null?-1:a.overall_similarity):av.similarityWeight;
    const bWeight=bv.similarityWeight==null?(b.overall_similarity==null?-1:b.overall_similarity):bv.similarityWeight;
    if (bWeight!==aWeight) return bWeight-aWeight;
    return (a.distance||0)-(b.distance||0) || String(a.id).localeCompare(String(b.id));
  });}
  function layerRows(){const layers=new Set(Array.from(document.querySelectorAll('[name=map_layer]:checked'),x=>x.value));return visibleRows().filter(r=>{const group=mapGroup(r);return layers.has(group)&&presentation.inMapRadius(r,snapshot.params,result,group);});}
  function comparisonRows(){return snapshot&&result?presentation.comparisonRows(result.reference_mode?visibleRows():layerRows(),snapshot.params,result,excluded):[];}
  function orderedComparisonRows(){const rows=comparisonRows();return ['nearest','reference_fallback'].includes(result?.selection_method)?[...rows].sort((a,b)=>a.distance-b.distance||String(a.id).localeCompare(String(b.id))):similarityOrder(rows);}
  function markerNumbers(){return presentation.numbering(visibleRows(),orderedComparisonRows());}
  function visibleMapRows(){return layerRows().filter(r=>!unselected.has(r.id));}
  function renderMap(){
    if(!map||!result)return;clearMap();drawCircles();if(!permissions.property_pins)return;
    const icons={propify:'Pin-propify.png',remax:'pin-remax.png',properati:'pin-properati.png'};
    const mode=$('cmp-marker-mode').value;
    const rows=visibleMapRows(),numbers=markerNumbers();
    rows.forEach(r=>{
      const number=String(numbers.get(String(r.id))),v=value(r),label=presentation.marker(r,v,mode,!permissions.portal_pins),dim=['reference','excluded','pending'].includes(v.status)&&!v.referenceUsed;
      const icon=permissions.portal_pins&&icons[r.source]?{url:'/static/requerimientos/data/'+icons[r.source],scaledSize:new google.maps.Size(32,40),anchor:new google.maps.Point(16,40),labelOrigin:new google.maps.Point(16,17)}:{path:'M 0 0 C -3 -7 -12 -17 -12 -25 A 12 12 0 1 1 12 -25 C 12 -17 3 -7 0 0 Z',scale:1,fillColor:r.kind==='Terreno'?'#d6a548':'#3789dd',fillOpacity:1,strokeColor:'#ffffff',strokeWeight:1,labelOrigin:new google.maps.Point(0,-25)};
      const marker=new google.maps.Marker({map,position:{lat:r.lat,lng:r.lng},title:r.title+' · '+Math.round(r.distance)+' m del inmueble objetivo · '+presentation.precision(r).label+' · '+label,opacity:dim?.55:1,zIndex:1000+Math.round((r.overall_similarity||0)*10),icon,label:{text:number,color:'#ffffff',fontSize:number.length>2?'9px':'11px',fontWeight:'700',className:'cmp-pin-number'}});
      marker.addListener('click',()=>selectMapRecord(r.id));markers.push(marker);
      markers.push(new google.maps.Marker({map,position:{lat:r.lat,lng:r.lng},clickable:false,opacity:dim?.55:1,zIndex:1001+Math.round((r.overall_similarity||0)*10),icon:{path:google.maps.SymbolPath.CIRCLE,scale:1,strokeOpacity:0,fillOpacity:0,labelOrigin:new google.maps.Point(0,12)},label:{text:label,fontSize:'10px',fontWeight:'600',className:'cmp-pin-label'}}));
      if(locatedIds.has(String(r.id))){
        marker.setOpacity(1);marker.setZIndex(100000);
        pulseMarkers.push(new google.maps.Marker({map,position:{lat:r.lat,lng:r.lng},icon:pulseIcon(0),clickable:false,zIndex:99999}));
      }
    });
    startMapPulses();
    const soilVisible=rows.some(row=>row.kind==='Terreno'&&row.distance>snapshot.params.radius);
    $('cmp-map-count').textContent=rows.length+' pines · radio '+decimals(snapshot.params.radius)+' m'+(soilVisible?' · suelo hasta '+decimals(result.land_radius)+' m':'');
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
    const warningCount=snapshot.warnings.length+(result.new?result.messages.length:0)+(diagnostic?1:0);
    $('cmp-notices').hidden=!warningCount;
    $('cmp-notices').open=!r.new&&warningCount>0;
    $('cmp-notices-label').textContent='Avisos del análisis ('+warningCount+')';
    if(r.model!=='components'){
      const basis=r.model==='land'?'terreno':'superficie construida';
      $('cmp-new').innerHTML='<h2>Valoración · '+escape(r.property_type)+'</h2><p class="cmp-muted">'+(r.house_count+r.land_count)+(r.reference_mode?' referencias seleccionadas':' comparables seleccionados')+'</p>'+(n?'<div class="cmp-line"><span>Mediana por m² de '+basis+'</span><strong>'+money(n.unit)+'/m²</strong></div><div class="cmp-total">'+money(n.total)+'</div><p class="cmp-muted">'+decimals(snapshot.params[n.area_basis])+' m² × '+money(n.unit)+'/m²</p>':'<p class="cmp-warning">'+r.messages.map(escape).join('<br>')+'</p>');
      return;
    }
    const usedHouses=Number.isFinite(r.usable_house_count)?r.usable_house_count:0;
    $('cmp-new').innerHTML='<h2>Valoración por componentes</h2><p class="cmp-muted">'+r.land_count+' terrenos usados · '+usedHouses+' casas usadas · suelo hasta '+r.land_radius+' m</p>'+
      (validSoil?'<div class="cmp-line"><span>Suelo de la microzona</span><strong>'+money(r.land_unit)+'/m²</strong></div>':'')+
      (n?'<div class="cmp-line"><span>Terreno objetivo</span><strong>'+money(n.land_value)+'</strong></div><div class="cmp-line"><span>Construcción y mejoras</span><strong>'+money(n.built_value)+'</strong></div><div class="cmp-total">'+money(n.total)+'</div>':'<p class="cmp-warning">'+r.messages.map(escape).join('<br>')+'</p>');
  }
  function medianExplanation(values){
    const ordered=[...values].sort((a,b)=>a-b),formatted=ordered.map(v=>money(v)+'/m²').join(', ');
    if(!ordered.length)return 'No hubo valores aptos.';
    if(ordered.length%2)return 'Ordenados: '+formatted+'. El valor central es '+money(ordered[Math.floor(ordered.length/2)])+'/m².';
    const left=ordered[ordered.length/2-1],right=ordered[ordered.length/2];
    return 'Ordenados: '+formatted+'. Se promedian los dos centrales: ('+money(left)+' + '+money(right)+') ÷ 2 = '+money((left+right)/2)+'/m².';
  }
  function calculationTable(headers,rows,rowClasses,rowAttrs,headerAttrs={}){return '<div class="cmp-calc-scroll"><table class="cmp-calc-table"><thead><tr>'+headers.map(h=>'<th'+(headerAttrs[h]?' '+headerAttrs[h]:'')+'>'+escape(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map((row,i)=>'<tr'+(rowClasses&&rowClasses[i]?' class="'+rowClasses[i]+'"':'')+(rowAttrs&&rowAttrs[i]?' '+rowAttrs[i]:'')+'>'+row.map(value=>'<td>'+value+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
  // Parecido de una casa con el inmueble objetivo: suma de las similitudes de
  // terreno y de construccion.
  function componentSimilarity(detail){return (detail.land_similarity||0)+(detail.built_similarity||0);}
  function renderComparison(){
    const type=snapshot?.params.property_type;
    const rows=snapshot&&result?comparisonRows():[],show=!!snapshot&&!!result;
    $('cmp-comparison').hidden=!show;
    $('cmp-comparison-open').hidden=!show;
    $('cmp-source-warning').hidden=!(snapshot?.warnings?.length);
    $('cmp-source-warning').textContent=(snapshot?.warnings||[]).join(' ');
    if(!show){$('cmp-comparison-content').replaceChildren();return;}
    $('cmp-comparison-title').textContent=result.reference_mode?'Referencias · '+rows.length+' más cercanas':result.valuation_mode==='land_only'?'Terrenos comparables · casa valorada como terreno':(type||'Propiedad')+'s comparables';
    $('cmp-comparison-open').textContent=result.reference_mode?'Mostrar cuadro de referencias en el mapa':'Mostrar cuadro de comparables en el mapa';
    const ordered=orderedComparisonRows(),numbers=markerNumbers();
    const surface=(area,similarity)=>area==null?'—':decimals(area)+' m²'+(similarity==null?'':' <span class="cmp-area-similarity '+(similarity<=70?'is-far':similarity<=90?'is-medium':'is-close')+'">('+decimals(similarity)+'%)</span>');
    const age=n=>n==null||!Number.isFinite(Number(n))||Number(n)<0?'—':Number(n)===0?'Estreno':decimals(n)+(Number(n)===1?' año':' años');
    const featureType=result.valuation_mode==='land_only'?'Terreno':type;
    const showParking=['Casa','Departamento'].includes(featureType), showFloor=featureType==='Departamento';
    const extraCells=row=>{
      const extra=presentation.comparisonFeatures(row);
      return [...(showParking?[
        '<span class="cmp-feature-value" title="'+escape(extra.parkingTitle)+'">'+escape(extra.parking)+'</span>',
        '<span class="cmp-feature-type" title="'+escape(extra.typeTitle)+'">'+escape(extra.type)+'</span>'
      ]:[]),...(showFloor?['<span class="cmp-feature-floor" title="'+escape(extra.floor==='—'?'Piso: sin información':'Piso: '+extra.floor)+'">'+escape(extra.floor)+'</span>']:[])];
    };
    const used=row=>{const v=value(row);return v.referenceUsed||v.recommended||v.status==='area'||(v.status==='land'&&v.selected);};
    const usage=row=>{const v=value(row);if(unselected.has(row.id))return 'Desmarcada';if(used(row))return result.reference_mode?'Referencia usada para valorar':'Usada para valorar';if(v.status==='reference'&&!v.referenceOnly)return 'Solo referencia';if(v.status==='excluded')return 'Desmarcada';return result.new?'Comparable no usado':'Sin valoración';};
    $('cmp-comparison-content').innerHTML=calculationTable(
      ['Seleccionar',...(permissions.portal_names?['Portal']:[]),'Precio\nanunciado','Terreno','Construcción','Antigüedad',...(showParking?['🚗','Tipo']:[]),...(showFloor?['🏢']:[]),'Distancia','Uso',...(permissions.publication?['Publicación']:[])],
      ordered.map(row=>['<label class="cmp-numbered-select"><input class="cmp-comparison-select" type="checkbox" data-map-select="'+escape(row.id)+'" '+(unselected.has(row.id)?'':'checked')+' aria-label="Mostrar en el mapa e incluir en el informe: '+escape('Propiedad '+numbers.get(String(row.id))+' · '+row.title)+'"><span class="cmp-comparable-number">'+numbers.get(String(row.id))+'</span></label>',...(permissions.portal_names?[escape(row.source.toUpperCase())]:[]),money(row.price),surface(row.land,row.land_similarity),surface(row.built,row.built_similarity),age(row.age),...extraCells(row),decimals(Math.round(row.distance))+' m',usage(row),...(permissions.publication?[row.url?'<a class="cmp-comparison-ad" href="'+escape(row.url)+'" target="_blank" rel="noopener noreferrer">Ver anuncio</a>':'<span>Sin enlace</span>']:[])]),
      ordered.map(row=>used(row)?'cmp-comparison-used':''),
      ordered.map(row=>'data-record="'+escape(row.id)+'"'),
      {'🚗':'class="cmp-feature-icon" scope="col" title="Cochera" aria-label="Cochera"',
       'Tipo':'scope="col" title="Tipo de cochera"',
       '🏢':'class="cmp-feature-icon" scope="col" title="Piso del departamento" aria-label="Piso del departamento"'}
    )+(ordered.length?'':'<p class="cmp-floating-empty">'+(result.reference_mode?'No hay referencias dentro del radio seleccionado.':'No hay comparables usados en las capas visibles del mapa.')+'</p>')+(window.ACMComparisonValuation?.markup(snapshot.params,result)||'');
    applySelectedRow();
    window.ACMComparisonValuation?.mount();
    updateReportButtons();
    document.dispatchEvent(new CustomEvent('acm:comparison-updated'));
  }
  function renderCalculationExplanation(){
    const host=$('cmp-calculation-explanation'),r=result,p=snapshot.params;
    if(r.model!=='components'){
      const basis=r.model==='land'?'terreno':'área construida',rows=r.breakdown.map(detail=>{const record=visibleRows().find(row=>row.id===detail.id);return [escape(record?.source?.toUpperCase()||''),escape(record?.code||detail.id),money(detail.price||record?.price),decimals(detail.area)+' m²',money(detail.offer_unit)+'/m²'];});
      host.innerHTML='<h3>1. Convertimos cada anuncio a una misma unidad</h3><p>Precio anunciado ÷ '+basis+' = precio por m².</p>'+calculationTable([permissions.portal_names?'Portal':'Comparable','Referencia','Precio','Área','Precio por m²'],rows)+'<h3>2. Tomamos el valor central</h3><p>'+escape(medianExplanation(r.breakdown.map(detail=>detail.offer_unit)))+'</p>'+(r.new?'<h3>3. Aplicamos el valor al inmueble objetivo</h3><p>'+decimals(p[r.new.area_basis])+' m² × '+money(r.new.unit)+'/m² = <strong>'+money(r.new.total)+'</strong>.</p>':'<p>No hubo comparables aptos para completar el cálculo.</p>');return;
    }
    const lands=r.land_ids.map(id=>visibleRows().find(row=>row.id===id)).filter(Boolean),landUnits=lands.map(row=>row.price/row.land);
    const details=r.breakdown.map(detail=>({detail,record:visibleRows().find(row=>row.id===detail.id)})).filter(item=>item.record),usable=details.filter(item=>item.detail.usable);
    if(r.built_unit_method==='primary_area_reference'&&r.new){
      const chosen=usable.find(item=>item.detail.id===r.built_reference_id);
      if(chosen){const {record,detail}=chosen;
        host.innerHTML='<h3>'+usable.length+' casa(s) usada(s) para valorar</h3>'+
          '<p>'+(usable.length===1?'Se usa una casa como referencia.':'Se promedian los precios ajustados de las casas seleccionadas.')+' Las demás quedan visibles para comparar y no intervienen.</p>'+
          '<p>Suelo: '+money(r.land_unit)+'/m², obtenido de '+lands.length+' terrenos de referencia. Construcción: '+money(detail.built_unit)+'/m², obtenido de esta casa después de descontar su terreno.</p>'+
          calculationTable(['Casa usada','Precio anunciado','Ajuste terreno','Ajuste construcción','Precio ajustado'],usable.map(item=>[escape(item.record.source.toUpperCase()+' · '+item.record.code),money(item.record.price),money(item.detail.land_adjustment),money(item.detail.built_adjustment),money(item.detail.target_estimate)]))+'<p>Valoración final: <strong>'+money(r.new.total)+'</strong>.</p>';
        return;
      }
    }
    let html='<h3>1. Calculamos el suelo con '+lands.length+' terreno(s)</h3><p>Cada terreno se convierte a precio por m²: precio anunciado ÷ área del terreno.</p>';
    if(lands.length)html+=calculationTable([permissions.portal_names?'Portal':'Comparable','Referencia','Operación'],lands.map(row=>[escape(row.source.toUpperCase()),escape(row.code),money(row.price)+' ÷ '+decimals(row.land)+' m² = <strong>'+money(row.price/row.land)+'/m²</strong>']))+'<p>'+escape(medianExplanation(landUnits))+' Se adopta <strong>'+money(r.land_unit)+'/m²</strong> para el suelo.</p>';
    else html+='<p>No hubo terrenos aptos; el proceso no puede separar suelo y construcción.</p>';
    html+='<h3>2. Separamos suelo y construcción en cada casa</h3><p>Precio de la casa − (área de terreno × valor del suelo) = remanente. Luego: remanente ÷ área construida = aporte por m² construido.</p>';
    if(details.length){const ordered=[...details].sort((a,b)=>(b.detail.similarity_weight||0)-(a.detail.similarity_weight||0)||componentSimilarity(b.detail)-componentSimilarity(a.detail)||(b.detail.overall_similarity||0)-(a.detail.overall_similarity||0)||String(a.detail.id).localeCompare(String(b.detail.id)));const isRecommended=item=>!!item.detail.recommended||item.detail.id===r.built_reference_id;const chosen=ordered.find(isRecommended);if(chosen)html+='<p class="cmp-calc-recommended-header"><span class="cmp-recommended">Recomendada</span> '+escape(chosen.record.source.toUpperCase()+' · '+chosen.record.code)+': es el comparable con mayor peso aplicado; las demás casas aptas también intervienen.</p>';html+=calculationTable(['Casa','Cálculo del remanente','Sim. terreno','Sim. construcción','Aporte por m²','Valor sugerido para el objetivo'],ordered.map(({record,detail})=>[escape(record.source.toUpperCase()+' · '+record.code),money(record.price)+' − ('+decimals(record.land)+' × '+money(r.land_unit)+') = '+money(detail.remainder),decimals(detail.land_similarity)+'%',decimals(detail.built_similarity)+'%',money(detail.built_unit)+'/m²',detail.usable?money(detail.target_estimate):'No participa · solo referencia']),ordered.map(item=>isRecommended(item)?'cmp-calc-row-recommended':''));}
    if(usable.length){
      const selected=usable.find(item=>item.detail.id===r.built_reference_id);
      html+='<p>'+(r.built_unit_method==='weighted_adjusted_prices'
        ?'Se ajusta cada anuncio al terreno y construcción objetivo. El resultado suma precio ajustado × peso aplicado. La similitud considera 45% terreno, 45% construcción y 10% distancia; los pesos son la similitud al cuadrado, normalizada al 100%. Son reglas iniciales pendientes de calibración.'
        :r.built_unit_method==='closest_built_similarity'&&selected
        ?'El aporte de construcción y mejoras se toma del comparable con la superficie construida más parecida al objetivo: <strong>'+escape(selected.record.source.toUpperCase()+' · '+selected.record.code)+'</strong>, con '+money(selected.detail.built_unit)+'/m² ('+decimals(selected.detail.built_similarity)+'% de similitud de construcción). Promediar metrajes muy distintos daba valores más bajos; las demás casas quedan como referencia.'
        :r.built_unit_method==='closest_comparable'&&selected
        ?'Solo hay dos casas y sus aportes están muy dispersos. Se usa el comparable más parecido a las superficies y la ubicación: <strong>'+escape(selected.record.source.toUpperCase()+' · '+selected.record.code)+'</strong>, con '+money(selected.detail.built_unit)+'/m². La otra casa permanece como referencia y no se promedian los extremos.'
        :r.built_unit_method==='weighted_median'
        ?'Los aportes están muy dispersos. Se usa una mediana ponderada por similitud: las casas con terreno, construcción y ubicación más parecidos tienen mayor peso.'
        :escape(medianExplanation(usable.map(item=>item.detail.built_unit))+' Este valor central es el aporte unitario aplicado al objetivo.'))+'</p>';
    }
    if(r.built_unit_method==='weighted_adjusted_prices')html+=calculationTable(['Comparable','Precio anunciado','Ajuste terreno','Ajuste construcción','Precio ajustado','Peso aplicado','Aporte al resultado'],[...usable].sort((a,b)=>b.detail.similarity_weight-a.detail.similarity_weight).map(({record,detail})=>[escape(record.source+' · '+record.code),money(record.price),money(detail.land_adjustment),money(detail.built_adjustment),money(detail.target_estimate),decimals(detail.similarity_weight)+'%',money(detail.weighted_contribution)]));
    html+='<h3>3. Aplicamos ambos componentes al inmueble objetivo</h3>';
    if(r.new)html+='<p>Suelo: '+decimals(p.land)+' m² × '+money(r.land_unit)+'/m² = <strong>'+money(r.new.land_value)+'</strong>.</p><p>Construcción y mejoras: '+decimals(p.built)+' m² × '+money(r.new.built_unit)+'/m² = <strong>'+money(r.new.built_value)+'</strong>.</p><p>Resultado: '+money(r.new.land_value)+' + '+money(r.new.built_value)+' = <strong>'+money(r.new.total)+'</strong>.</p><p>Las casas usadas sugieren valores individuales entre <strong>'+money(r.new.range_low)+'</strong> y <strong>'+money(r.new.range_high)+'</strong> para el inmueble objetivo.</p>';
    else html+='<p>No se completó este paso porque faltó un componente válido.</p>';
    host.innerHTML=html;
  }
  function galleryAction(r){return '';}
  function photo(r){return r.image?'<img src="'+escape(r.image)+'" loading="lazy" alt="Foto del anuncio" role="button" tabindex="0" aria-label="Ver fotos de la propiedad" data-property-gallery="'+escape(r.gallery_url||'')+'" data-gallery-cover="'+escape(r.image)+'">':'<div class="cmp-photo-empty">Sin foto</div>';}
  function precisionBadge(r){const p=presentation.precision(r);return '<span class="cmp-precision '+p.kind+'">'+escape(p.label)+'</span>';}
  function publicationBadge(r){if(!permissions.metadata)return '';const labels={activa:'Activa',posible_retirada:'Posible retirada',retirada:'Retirada',sin_verificar:'Sin verificar'};const state=labels[r.state]||'Sin verificar';const misses=r.consecutive_absences?' · '+r.consecutive_absences+' ausencia(s)':'';return '<span class="cmp-publication-state state-'+escape(r.state||'sin_verificar')+'">Publicación: '+escape(state+misses)+'</span>';}
  function similarityBlock(r){const overall=r.overall_similarity;if(overall==null)return '';const v=value(r);const weight=v.similarityWeight==null?'':'<span>Peso en cálculo '+decimals(v.similarityWeight)+'%</span>';return '<div class="cmp-similarity cmp-similarity-visible"><strong>Similitud con tu inmueble: '+decimals(overall)+'%</strong><span>Terreno '+decimals(r.land_similarity)+'%</span><span>Construcción '+decimals(r.built_similarity)+'%</span><span>Distancia '+decimals(r.distance_similarity)+'%</span>'+weight+'</div>';}
  function suggestedBadge(r){
    const review=(aiProposal?.reviews||snapshot?.params?.ai_review_recommendations||[]).find(item=>String(item.id)===String(r.id));
    if(review)return '<div class="cmp-ai-suggested">Recomendada por la IA · completar datos antes de usar</div><p class="cmp-muted">'+escape(review.reason)+'<br>'+escape(review.missing.join(' · '))+'</p>';
    if(!aiProposal?.ids.some(id=>String(id)===String(r.id)))return '';
    return '<div class="cmp-ai-suggested">Recomendada por la IA · '+(value(r).recommended?'ya usada en el cálculo actual':'pendiente de aplicar')+'</div>';
  }
  function heading(r,selection){const offer=presentation.offer(r);return suggestedBadge(r)+'<div class="cmp-card-top">'+photo(r)+'<div class="cmp-card-main"><div class="cmp-card-sub">'+escape(r.source.toUpperCase())+' · '+Math.round(r.distance)+' m</div><div class="cmp-card-title">'+escape(r.title)+'</div><div class="cmp-card-sub"><strong>'+escape(offer.operation)+'</strong> · '+escape(offer.totalLabel)+'</div><div class="cmp-card-price">'+money(r.price)+'</div><div class="cmp-card-sub">'+escape(offer.unitLabel)+': <strong>'+(offer.unit==null?'Sin área informada':money(offer.unit)+'/m²')+'</strong></div><div class="cmp-card-sub">'+escape(r.kind)+' · '+escape(r.district||'Sin distrito')+'</div>'+precisionBadge(r)+' '+publicationBadge(r)+similarityBlock(r)+'</div>'+(selection&&!r.issues.length?'<label><input type="checkbox" data-include="'+escape(r.id)+'" '+(!excluded.has(r.id)?'checked':'')+' aria-label="Incluir '+escape(r.title)+'"> Incluir</label>':'')+'</div>';}
  function areas(r){return '<div class="cmp-card-areas"><span>Área de terreno<strong>'+decimals(r.land)+(r.land?' m²':'')+'</strong></span><span>Área construida<strong>'+decimals(r.built)+(r.built?' m²':'')+'</strong></span></div>';}
  function features(r){return r.kind==='Terreno'?'':'<p class="cmp-card-sub">Antigüedad: '+age(r.age)+' · Habitaciones: '+decimals(r.rooms)+' · Baños: '+decimals(r.baths)+(r.kind!=='Casa'?' · Piso: '+escape(r.floor_label??decimals(r.floor)):'')+'</p>';}
  function breakdown(r){
    const v=value(r);
    if(v.referenceUsed)return '<section class="cmp-breakdown"><h3>Referencia usada para valorar</h3><p>'+money(v.offerUnit)+'/m² × área objetivo = <strong>'+money(v.adjustedTotal)+'</strong>.</p><p class="cmp-issues">'+escape(v.reason)+'</p></section>';
    if(v.status==='area')return '<section class="cmp-breakdown"><h3>'+escape(r.kind)+' · comparable por superficie construida</h3><div class="cmp-breakdown-grid"><div><span>Oferta por m² construido</span><strong>'+money(v.offerUnit)+'/m²</strong></div><div><span>Aplicada al área objetivo</span><strong>'+money(v.adjustedTotal)+'</strong></div></div><p class="cmp-equation">Se compara con inmuebles del mismo tipo; no se presenta como valor de suelo independiente.</p></section>';
    if(v.status==='land')return '<section class="cmp-breakdown"><h3>Terreno · referencia del suelo</h3><div class="cmp-breakdown-grid"><div><span>Oferta por m² de terreno</span><strong>'+money(v.offerUnit)+'/m²</strong></div><div><span>Uso en este análisis</span><small>'+(v.selected?'Incluido en la mediana del suelo':'Fuera del radio requerido; no participa')+'</small></div></div></section>';
    if(result.built_unit_method==='primary_area_reference'&&(v.recommended||v.referenceOnly))return '<section class="cmp-breakdown"><h3>'+(v.recommended?'Propiedad usada para valorar':'Solo referencia · no interviene')+'</h3><p>'+money(r.price)+' + '+money(v.landAdjustment)+' por terreno + '+money(v.builtAdjustment)+' por construcción = <strong>'+money(v.targetEstimate)+'</strong></p><p>'+(v.recommended?(result.usable_house_count===1?'Este es el resultado final para tu inmueble.':'Esta estimación se promedia con las otras casas usadas.'):'Estimación individual solo para comparar. '+escape(v.reason))+'</p></section>';
    if(!['house','review'].includes(v.status))return '<p class="cmp-issues">'+escape(v.reason)+'</p>';
    return '<section class="cmp-breakdown '+(v.status==='review'?'review':'')+'"><h3>Valor atribuido por este anuncio '+(v.recommended?'<span class="cmp-recommended">Recomendada · '+decimals(v.similarityWeight)+'% de peso</span>':'')+'</h3><div class="cmp-breakdown-grid"><div><span>Valor del terreno</span><strong>'+money(v.landValue)+'</strong><small>'+money(v.landUnit)+'/m² de suelo</small></div><div><span>Construcción y mejoras</span><strong>'+money(v.remainder)+'</strong><small>'+money(v.builtUnit)+'/m² construido</small></div><div><span>Valor que sugiere para el inmueble objetivo</span><strong>'+(v.status==='review'?'No participa':money(v.targetEstimate))+'</strong><small>'+(v.status==='review'?'Remanente no positivo · solo referencia':decimals(snapshot.params.land)+' m² terreno + '+decimals(snapshot.params.built)+' m² construidos')+'</small></div></div><div class="cmp-similarity"><span>Similitud con el objetivo</span><span>Terreno <strong>'+decimals(v.landSimilarity)+'%</strong></span><span>Construcción <strong>'+decimals(v.builtSimilarity)+'%</strong></span><span>Distancia <strong>'+decimals(v.distanceSimilarity)+'%</strong></span><span>Total <strong>'+decimals(v.overallSimilarity)+'%</strong></span><span>Peso aplicado <strong>'+decimals(v.similarityWeight)+'%</strong></span></div><p class="cmp-equation">'+money(r.price)+' − ('+decimals(r.land)+' m² × '+money(v.landUnit)+'/m²) = '+money(v.remainder)+' en construcción y mejoras.</p>'+(v.landAdjustment!=null?'<p class="cmp-equation">Precio '+money(r.price)+' + ajuste terreno ('+money(v.landAdjustment)+') + ajuste construcción ('+money(v.builtAdjustment)+') = <strong>'+money(v.targetEstimate)+'</strong>. Peso aplicado: '+decimals(v.similarityWeight)+'%; aporta '+money(v.weightedContribution)+' al resultado.</p>':'')+(v.reason?'<p class="cmp-issues">'+escape(v.reason)+'</p>':'')+'</section>';
  }
  function badge(r){const v=value(r);const text={area:'Incluida en el análisis',house:'Incluida en el análisis',review:'Requiere revisión',land:v.selected?'Terreno incluido':'Terreno de referencia',reference:'Solo referencia',excluded:'Desmarcada',pending:'Cálculo pendiente'};return '<span class="cmp-badge '+(['house','land','area'].includes(v.status)?'':'ref')+'">'+text[v.status]+'</span>';}
  function inclusion(r){return r.issues.length?'':'<label><input type="checkbox" data-include="'+escape(r.id)+'" '+(!excluded.has(r.id)?'checked':'')+' aria-label="Incluir '+escape(r.title)+'"> Incluir</label>';}
  function fixImages(container){container.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{const empty=document.createElement('div');empty.className='cmp-photo-empty';empty.textContent='Sin foto';img.replaceWith(empty);},{once:true}));}
  function renderCards(){
    const rows=visibleRows(),houses=comparableRows(),lands=rows.filter(r=>mapGroup(r)==='land'),refs=rows.filter(r=>!['property','land'].includes(mapGroup(r)));
    $('cmp-house-count').textContent=houses.length;$('cmp-land-count').textContent=lands.length;$('cmp-ref-count').textContent=refs.length;
    const propertyType=snapshot.params.property_type,found=rows.filter(r=>r.kind===propertyType).length;
    const used=result?.built_unit_method==='primary_area_reference'?result.usable_house_count:houses.length;
    $('cmp-counts').textContent=found+' '+propertyType.toLowerCase()+(found===1?' encontrada':'s encontradas')+' · '+used+' comparables usados · '+lands.length+' terrenos usados · '+(refs.length+houses.length-used)+' solo referencia';
    $('cmp-map-count').textContent=rows.length+' propiedades';
    document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
    const selected=tab==='reference'?refs:tab==='Casa'?houses:lands;
    $('cmp-cards').innerHTML=similarityOrder(selected).map(r=>'<article class="cmp-card'+(value(r).recommended?' cmp-card-used':'')+'" data-record="'+escape(r.id)+'">'+(value(r).recommended?'<div class="cmp-used-label">Propiedad usada para valorar</div>':'')+heading(r,false)+areas(r)+features(r)+'<details class="cmp-card-calculation"><summary>Desglose y operaciones del comparable</summary>'+breakdown(r)+'</details><div class="cmp-card-footer">'+badge(r)+'<div class="cmp-card-actions">'+inclusion(r)+galleryAction(r)+'<button type="button" data-detail="'+escape(r.id)+'">Ver detalle ↗</button></div></div><button type="button" class="cmp-locate" data-locate="'+escape(r.id)+'" aria-pressed="'+locatedIds.has(String(r.id))+'">'+(locatedIds.has(String(r.id))?'Dejar de palpitar en el mapa':'Buscar propiedad en el mapa')+'</button></article>').join('')||'<p class="cmp-muted">No hay registros en este grupo.</p>';
    fixImages($('cmp-cards'));
  }
  function detailMarkup(r){
    const recordFact=r.record_id?'<div>Registro interno<strong>#'+escape(r.record_id)+'</strong></div>':'';
    const editAction=r.photo_review?'<button type="button" data-photo-review="'+escape(r.photo_review)+'" data-approved="true">Autorizar foto sin marcas de origen</button><button type="button" data-photo-review="'+escape(r.photo_review)+'" data-approved="false">Restringir foto con marcas de origen</button>':'';

    const lifecycle=(permissions.publication_dates?'<div>Primera vez vista<strong>'+escape(formatDate(r.first_seen))+'</strong></div>':'')+(permissions.last_seen?'<div>Última vez vista<strong>'+escape(formatDate(r.last_seen))+'</strong></div>':'')+(permissions.metadata?'<div>Primera ausencia<strong>'+escape(formatDate(r.first_missing))+'</strong></div><div>Retiro confirmado<strong>'+escape(formatDate(r.retired_at))+'</strong></div>':'');
    $('cmp-detail-content').innerHTML=heading(r,false)+areas(r)+features(r)+breakdown(r)+'<div class="cmp-detail-facts">'+recordFact+'<div>Ubicación<strong>'+escape(presentation.precision(r).label)+'</strong></div><div>Operación<strong>'+escape(presentation.offer(r).operation)+'</strong></div>'+(permissions.metadata?'<div>Disponibilidad<strong>'+publicationBadge(r)+'</strong></div>':'')+lifecycle+'<div>Distancia<strong>'+decimals(r.distance)+' m</strong></div><div>Precio<strong>'+(r.converted?'Convertido de soles a 3,44':'USD')+'</strong></div><div>Estado en ACM<strong>'+badge(r)+'</strong></div></div>'+(r.description?'<details><summary>Descripción del anuncio</summary><p class="cmp-description">'+escape(r.description)+'</p></details>':'')+'<p class="cmp-muted">En casas, construcción y mejoras, el remanente se calcula después de descontar el suelo estimado. Una publicación retirada permanece visible como referencia y no participa en el cálculo.</p><div class="cmp-card-footer">'+(r.url?'<a href="'+escape(r.url)+'" target="_blank" rel="noopener noreferrer">Abrir publicación ↗</a>':'')+(r.portal_url?'<a href="'+escape(r.portal_url)+'" target="_blank" rel="noopener noreferrer">Ir al portal ↗</a>':'')+galleryAction(r)+editAction+'</div>';
    fixImages($('cmp-detail-content'));
  }
  function openDetail(id){detailId=id;renderDetail();if(!$('cmp-detail').open)$('cmp-detail').showModal();}
  function renderDetail(){if(!detailId||!snapshot)return;const r=snapshot.records.find(row=>row.id===detailId);if(!r)return;detailMarkup(r);}
  // Tarjeta lateral: muestra solo la propiedad elegida con un pin del mapa.
  function selectedRecord(){return selectedMapId==null?null:((snapshot?.records||[]).find(row=>String(row.id)===selectedMapId)||null);}
  function setSelectedCardOpen(open){
    const content=$('cmp-selected-content'),toggle=$('cmp-selected-toggle'),card=$('cmp-selected-card');
    if(!content||!toggle)return;
    content.hidden=!open;
    toggle.setAttribute('aria-expanded',String(!!open));
    if(card)card.classList.toggle('is-open',!!open);
    if(selectedMapId!=null)setSidePanel(!!open);
  }
  function renderSelectedCard(){
    const host=$('cmp-selected-content'),hint=$('cmp-selected-hint');
    if(!host)return;
    const row=selectedRecord();
    if(!row){
      host.innerHTML='<p class="cmp-selected-empty">Haz clic en un pin del mapa para ver aquí solo esa propiedad.</p>';
      if(hint)hint.textContent='Haz clic en un pin';
      return;
    }
    const dialogHost=$('cmp-detail-content'),previous=detailId;
    detailId=row.id;detailMarkup(row);detailId=previous;
    host.innerHTML=dialogHost.innerHTML;
    fixImages(host);
    if(hint)hint.textContent=(row.source||'').toUpperCase()+' · '+money(row.price);
  }
  function applySelectedRow(){
    const host=$('cmp-comparison-content');
    if(!host)return;
    host.querySelectorAll('tr.cmp-row-selected').forEach(tr=>tr.classList.remove('cmp-row-selected'));
    if(selectedMapId==null)return;
    host.querySelectorAll('tr[data-record]').forEach(tr=>{if(tr.dataset.record===selectedMapId)tr.classList.add('cmp-row-selected');});
  }
  function selectMapRecord(id){
    const row=(snapshot?.records||[]).find(r=>String(r.id)===String(id));
    if(!row)return;
    selectedMapId=String(row.id);
    const card=$('cmp-selected-card');if(card)card.hidden=false;
    renderSelectedCard();
    setSelectedCardOpen(true);
    applySelectedRow();
    setSidePanel(true);
    if(map)map.panTo({lat:row.lat,lng:row.lng});
  }
  function clearSelectedRecord(){
    selectedMapId=null;
    renderSelectedCard();
    setSelectedCardOpen(false);
    applySelectedRow();
    const card=$('cmp-selected-card');if(card)card.hidden=true;
    setSidePanel(false);
  }
  // El panel derecho solo existe cuando hay un pin elegido, y muestra solo esa propiedad.
  function setSidePanel(show){
    const sidebar=$('cmp-results'),resizer=$('cmp-resizer');
    if(sidebar){sidebar.hidden=!show;sidebar.classList.toggle('cmp-only-selection',!!show);}
    if(resizer)resizer.hidden=!show;
    if(map&&typeof google!=='undefined'&&google.maps){
      google.maps.event.trigger(map,'resize');
      window.dispatchEvent(new Event('resize'));
    }
  }
  function selection(){const manual=(permissions.adjust_valuation?window.ACMComparisonValuation?.value():null);return {token:snapshot.token,excluded:[...new Set([...excluded,...(result?.reference_mode?unselected:[])])],report_ids:comparisonRows().filter(row=>!unselected.has(row.id)).map(row=>row.id),...(permissions.adjust_valuation?{manual_valuation:manual}:{}),...(permissions.report_notes?{report_notes:window.ACMComparisonValuation?.notes()||''}:{}),...(snapshot.params.weight_reference?{target_areas:{land:snapshot.params.land,built:snapshot.params.built}}:{})};}
  const perspectiveForm=$('acm-perspective-form');
  perspectiveForm?.addEventListener('submit',event=>{
    if(!snapshot||!result)return;
    if(window.ACMComparisonValuation?.valid()===false){event.preventDefault();$('cmp-status').textContent='Corrige el valor ajustado antes de cambiar de vista.';return;}
    const data=selection();
    const center=map?.getCenter();
    data.ui={hidden_ids:[...unselected],layers:Array.from(document.querySelectorAll('[name=map_layer]:checked'),input=>input.value),
      ...(center?{viewport:{lat:center.lat(),lng:center.lng(),zoom:map.getZoom()}}:{})};
    let field=perspectiveForm.querySelector('[name="analysis_selection"]');
    if(!field){field=document.createElement('input');field.type='hidden';field.name='analysis_selection';perspectiveForm.append(field);}
    field.value=JSON.stringify(data);
  });
  function setReportMenu(open){
    const menu=$('cmp-comparison-downloads');menu.hidden=!open;$('cmp-comparison-report').setAttribute('aria-expanded',String(open));
    if(open){menu.classList.remove('opens-up');menu.classList.toggle('opens-up',menu.getBoundingClientRect().bottom>$('map-container').getBoundingClientRect().bottom-8);}
  }
  function updateReportButtons(){const none=reportDownloading||window.ACMComparisonValuation?.valid()===false||!result?.new||!comparisonRows().some(row=>!unselected.has(row.id));['cmp-word','cmp-pdf','cmp-html','cmp-comparison-report','cmp-save'].forEach(id=>$(id).disabled=none);document.querySelectorAll('[data-report-format]').forEach(button=>button.disabled=none);if(none)setReportMenu(false);}
  $('cmp-comparison-content').addEventListener('change',async event=>{
    const id=event.target.dataset.mapSelect;if(!id||!snapshot)return;
    event.target.checked?unselected.delete(id):unselected.add(id);renderMap();updateReportButtons();$('cmp-save').textContent='Guardar en historial';
    if(!result.reference_mode){$('cmp-status').textContent='Marcadores e informe actualizados con las propiedades marcadas.';return;}
    const payload=selection(),seq=++sequence;$('cmp-status').textContent='Recalculando con las referencias marcadas…';
    ['cmp-word','cmp-pdf','cmp-html','cmp-comparison-report','cmp-save'].forEach(key=>$(key).disabled=true);
    try{const data=await post('calcular',payload);if(seq!==sequence)return;result=data.result;snapshot.params=data.params;render(false);$('cmp-status').textContent='Cálculo actualizado con las referencias marcadas.';}
    catch(error){if(seq===sequence){clearResult('No se pudo actualizar el cálculo con referencias. Reintenta la búsqueda.');$('cmp-status').textContent=error.message;}}
  });
  document.addEventListener('acm:report-notes-changed',()=>{updateReportButtons();$('cmp-save').textContent='Guardar en historial';});
  document.addEventListener('acm:valuation-adjusted',()=>{const total=(permissions.adjust_valuation?window.ACMComparisonValuation?.value():null)??result?.new?.total;const displayed=$('cmp-new').querySelector('.cmp-total');if(displayed&&total!=null)displayed.textContent=money(total,2);updateReportButtons();$('cmp-save').textContent='Guardar en historial';});
  function renderSimple(){
    const host=$('cmp-simple');host.hidden=!aiExplanation;
    $('cmp-ai-title').textContent=aiProposal?'Propuesta de la IA · pendiente de aplicar':'Explicación del resultado';
    host.textContent=aiExplanation||'';
  }
  function renderProposal(){
    $('cmp-proposal').hidden=!aiProposal;
    if(!aiProposal)return;
    const rows=aiProposal.ids.map(id=>visibleRows().find(row=>String(row.id)===String(id))).filter(Boolean);
    $('cmp-proposal-apply').disabled=!rows.length||!aiProposal.result?.new;
    $('cmp-ai-open').textContent='Recomendaciones de la IA'+((aiProposal.reviews||[]).length?' · '+aiProposal.reviews.length+' para revisar':'');
    $('cmp-proposal-summary').innerHTML=(rows.length?'<p><strong>Resultado actual: '+money(result.new?.total)+'. Con la propuesta: '+money(aiProposal.result.new?.total)+'.</strong><br>Se aplicará al pulsar «Usar estos comparables».</p>':'')+rows.map(row=>'<div class="cmp-ai-proposal-row"><strong>'+money(row.price)+' anunciado · '+escape(row.source.toUpperCase())+' · '+escape(row.district||row.title)+'</strong><span>Terreno '+decimals(row.land)+' m² · Construcción '+decimals(row.built)+' m² · Antigüedad '+age(row.age)+' · '+Math.round(row.distance)+' m</span><button type="button" data-proposal-detail="'+escape(row.id)+'">Ver esta propiedad</button></div>').join('')+(aiProposal.reviews||[]).map(review=>'<div class="cmp-ai-proposal-row"><strong>Recomendada por la IA · pendiente de completar</strong><span>'+escape(review.reason)+'</span><span>'+escape(review.missing.join(' · '))+'</span><span>Completa el dato y vuelve a buscar antes de incluirla en el cálculo.</span><button type="button" data-proposal-detail="'+escape(review.id)+'">Ver referencia</button></div>').join('');
    renderCards();renderDetail();
  }
  $('cmp-proposal').addEventListener('click',event=>{
    const button=event.target.closest('[data-proposal-detail]');
    if(button){const row=visibleRows().find(r=>String(r.id)===button.dataset.proposalDetail);if(row)openDetail(row.id);}
  });
  $('cmp-ai-open').addEventListener('click',()=>{if(snapshot&&!$('cmp-ai-dialog').open)$('cmp-ai-dialog').showModal();});
  $('cmp-ai-close').addEventListener('click',()=>$('cmp-ai-dialog').close());
  async function explainAutomatically(){
    if(!permissions.ai)return;
    if(!snapshot||!snapshot.records.length)return;
    const key=JSON.stringify(selection()),seq=sequence;
    const current=new AbortController();aiController=current;
    const timer=setTimeout(()=>current.abort(),140000);
    $('cmp-ai-panel').hidden=false;$('cmp-ai-status').textContent='Analizando resultado…';
    try{
      const response=await fetch($('cmp-ai-panel').dataset.url,{method:'POST',credentials:'same-origin',signal:current.signal,
        headers:{'Content-Type':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value},body:key});
      if(!response.headers.get('content-type')?.includes('application/json'))throw Error('El servidor no devolvió datos. Revisa tu sesión.');
      const body=await response.json();if(!response.ok)throw Error(body.error||'No se pudo generar la explicación.');
      if(aiController!==current||seq!==sequence||!snapshot||key!==JSON.stringify(selection()))return;
      if(body.current_token){snapshot.token=body.current_token;snapshot.params=body.current_params;}
      aiExplanation=body.explanation;aiProposal=body.proposal||null;renderSimple();$('cmp-ai-status').textContent='';
      renderProposal();
    }catch(error){if(aiController===current&&seq===sequence)$('cmp-ai-status').textContent=error.name==='AbortError'?'La explicación tardó demasiado. El cálculo se conserva.':error.message;}
    finally{clearTimeout(timer);if(aiController===current)aiController=null;}
  }
  $('cmp-proposal-apply').addEventListener('click',()=>{
    if(!aiProposal?.ids.length||!aiProposal.result?.new||!snapshot)return;
    const proposal=aiProposal,explanation=aiExplanation;
    snapshot.token=proposal.token;snapshot.params=proposal.params;result=proposal.result;
    $('cmp-ai-dialog').close();
    render(false);aiExplanation=explanation;renderSimple();$('cmp-ai-panel').hidden=false;
    $('cmp-ai-status').textContent='Propuesta aplicada.';
  });
  function render(askAI=true){
    if(aiController)aiController.abort();aiController=null;aiExplanation=null;
    $('cmp-ai-panel').hidden=!snapshot.records.length;$('cmp-ai-status').textContent='';
    $('cmp-ai-open').disabled=!snapshot.records.length;$('cmp-ai-open').textContent='Recomendaciones de la IA';
    aiProposal=null;$('cmp-proposal').hidden=true;
    if(result.reference_mode){const key=result.model==='land'?'other_reference':'property_reference';document.querySelector('[name=map_layer][value='+key+']').checked=true;}
    result.breakdown.forEach(d=>{const row=snapshot.records.find(r=>r.id===d.id);if(row)for(const key of ['land_similarity','built_similarity','distance_similarity','overall_similarity'])if(d[key]!=null)row[key]=d[key];});
    renderSummary();renderCalculationExplanation();renderComparison();renderCards();renderMap();renderDetail();renderSimple();$('cmp-export').disabled=false;$('cmp-word').disabled=!result.new;$('cmp-pdf').disabled=!result.new;$('cmp-save').disabled=!result.new;
    updateReportButtons();
    $('cmp-calculation-open').disabled=false;
    $('cmp-scenario').hidden=result.model!=='components'||!result.new;
    $('cmp-scenario-land').value=snapshot.params.land;$('cmp-scenario-built').value=snapshot.params.built;
    document.dispatchEvent(new CustomEvent('acm:result',{detail:{available:!!result.new}}));
    if(askAI&&!result.reference_mode)explainAutomatically();
  }
  $('cmp-scenario-apply').addEventListener('click',async()=>{
    if(!snapshot||result?.model!=='components')return;
    const land=Number($('cmp-scenario-land').value),built=Number($('cmp-scenario-built').value);
    if(!(land>0&&built>0&&land<=1000000&&built<=1000000)){$('cmp-status').textContent='Completa ambas superficies con valores positivos.';return;}
    const payload={...selection(),target_areas:{land,built}},seq=++sequence;
    clearResult('Ajustando superficies con la misma muestra…');
    try{const data=await post('calcular',payload);if(seq!==sequence)return;
      snapshot.params=data.params;result=data.result;form.elements.land.value=land;form.elements.built.value=built;render();
      $('cmp-status').textContent='Escenario actualizado: misma muestra y pesos de la búsqueda inicial. Al cambiar la selección manual cambian las referencias.';
    }catch(error){if(seq===sequence)$('cmp-status').textContent=error.message;}
  });
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(!permissions.calculate)return;if(form.dataset.authenticated==='false'){requestLogin();return;}const p=input();if(!p.sources.length){$('cmp-status').textContent='Selecciona al menos una fuente.';return;}
    searching=true;setLocationLocked(true);setSearchFormCollapsed(true);$('cmp-search-message').hidden=true;
    const seq=++sequence;snapshot=null;excluded.clear();unselected.clear();locatedIds.clear();if($('cmp-detail').open)$('cmp-detail').close();clearResult('Buscando comparables…');$('cmp-search').disabled=true;$('cmp-status').textContent='Buscando comparables del tipo seleccionado…';
    try{const data=await post('buscar',p);if(seq!==sequence)return;snapshot=data;result=data.result;tab=p.property_type==='Terreno'||result.valuation_mode==='land_only'?'Terreno':'Casa';render();fitSearchRadius();document.dispatchEvent(new CustomEvent('acm:search-completed',{detail:{lat:p.lat,lng:p.lng}}));$('cmp-status').textContent='Análisis actualizado. Desmarca comparables para recalcular el mapa, las tarjetas y el resultado.';}
    catch(error){if(seq===sequence){snapshot=null;setLocationLocked(false);setSearchFormCollapsed(false);clearResult('La búsqueda no terminó. Reintenta.');$('cmp-status').textContent=error.message;$('cmp-search-message').textContent=error.message;$('cmp-search-message').hidden=false;}}
    finally{if(seq===sequence){searching=false;setSearchFormCollapsed(form.hidden);$('cmp-search').disabled=false;}}
  });
  $('cmp-form-toggle').addEventListener('click',()=>{
    if(searching)return;
    if(form.hidden)reopenSearch();
    else setSearchFormCollapsed(true);
  });
  $('cmp-move-pin').addEventListener('click',reopenSearch);
  $('cmp-new-acm').addEventListener('click',()=>{
    if(searching)return;
    // Restablecer antes de recargar evita recuperar los campos anteriores del navegador.
    form.reset();$('cmp-address').value='';window.location.assign(window.location.pathname.includes('analisis-pruebas')?'/acm/analisis-pruebas/':'/acm/analisis/');
  });
  form.addEventListener('input',e=>{if(e.target.name){if(['property_type','age','built'].includes(e.target.name))configureType();$('cmp-radius-label').textContent=form.elements.radius.value+' m';invalidate();}});
  form.addEventListener('change',e=>{if(e.target.name){if(['property_type','age','built'].includes(e.target.name))configureType();invalidate();}});
  $('cmp-address').addEventListener('keydown',e=>{if(e.key==='Enter')e.preventDefault();});
  document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{tab=button.dataset.tab;if(snapshot)renderCards();}));
  $('cmp-marker-mode').addEventListener('change',renderMap);
  document.querySelectorAll('[name=map_layer]').forEach(input=>input.addEventListener('change',()=>{renderMap();if(snapshot&&result)renderComparison();}));
  $('cmp-cards').addEventListener('click',e=>{const locate=e.target.closest('[data-locate]');if(locate){locateProperty(locate.dataset.locate);return;}const button=e.target.closest('[data-detail]');if(button)openDetail(button.dataset.detail);});
  $('cmp-detail-close').addEventListener('click',()=>$('cmp-detail').close());
  $('cmp-selected-toggle')?.addEventListener('click',()=>setSelectedCardOpen($('cmp-selected-content').hidden));
  $('cmp-selected-close')?.addEventListener('click',clearSelectedRecord);
  $('cmp-calculation-open').addEventListener('click',()=>{if(snapshot&&!$('cmp-calculation').open)$('cmp-calculation').showModal();});
  $('cmp-comparison-open').addEventListener('click',()=>{
    if(!snapshot||!result)return;
    renderComparison();
    document.dispatchEvent(new CustomEvent('acm:comparison-updated',{detail:{reposition:true}}));
    requestAnimationFrame(()=>$('cmp-comparison').scrollIntoView({block:'nearest',behavior:'smooth'}));
  });
  $('cmp-calculation-close').addEventListener('click',()=>$('cmp-calculation').close());
  $('cmp-calculation').addEventListener('click',e=>{if(e.target===$('cmp-calculation')){const b=e.target.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)e.target.close();}});
  document.addEventListener('acm:workspace-resize',()=>{if(map){const center=map.getCenter();google.maps.event.trigger(map,'resize');if(center)map.setCenter(center);}});
  $('cmp-detail-content').addEventListener('click',e=>{const button=e.target.closest('[data-edit-record]');if(button&&typeof window.openScrapedEditor==='function')window.openScrapedEditor(button.dataset.editRecord);});
  $('cmp-detail').addEventListener('close',()=>{detailId=null;});
  $('cmp-detail').addEventListener('click',e=>{if(e.target===$('cmp-detail')){const b=e.target.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)e.target.close();}});
  $('cmp-cards').addEventListener('change',async e=>{
    const id=e.target.dataset.include;if(!id||!snapshot)return;e.target.checked?excluded.delete(id):excluded.add(id);const seq=++sequence;
    const payload=selection();
    clearResult('Actualizando selección…');$('cmp-status').textContent='Recalculando suelo y construcción de cada casa…';
    try{const data=await post('calcular',payload);if(seq!==sequence)return;result=data.result;snapshot.params=data.params;render();$('cmp-status').textContent='Mapa, propiedades y valoración actualizados con tu selección.';}
    catch(error){if(seq===sequence){clearResult('No se pudo aplicar la selección. Busca nuevamente.');$('cmp-status').textContent=error.message;}}
  });
  $('cmp-export').addEventListener('click',()=>{
    if(!permissions.export||!snapshot||!result)return;const file={fecha:new Date().toISOString(),parametros:snapshot.params,advertencias:snapshot.warnings,excluidos:[...excluded],resultado:result,comparables:visibleRows().map(r=>({...r,analisis:value(r)}))};
    const url=URL.createObjectURL(new Blob([JSON.stringify(file,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='acm-componentes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('cmp-save').addEventListener('click',async()=>{
    if(!snapshot||!result||!result.new||window.ACMComparisonValuation?.valid()===false)return;const button=$('cmp-save');button.disabled=true;$('cmp-status').textContent='Guardando análisis y selección en el historial…';
    try{const data=await post('guardar',selection());button.textContent='Guardado · '+data.code;$('cmp-status').textContent=data.created?'Análisis guardado en el historial.':'Este mismo análisis ya estaba guardado en el historial.';}
    catch(error){$('cmp-status').textContent=error.message;button.disabled=false;}
  });
  function reportStatus(message){const host=$('cmp-report-status');if(host){host.textContent=message;host.hidden=!message;}}
  async function downloadReport(url,extension,label){
    if(!snapshot||!result?.new||reportDownloading||window.ACMComparisonValuation?.valid()===false||!comparisonRows().some(row=>!unselected.has(row.id)))return;reportDownloading=true;updateReportButtons();let downloaded=false;$('cmp-status').textContent='Generando informe '+label+' con las operaciones del análisis…';reportStatus('Generando informe '+label+'…');
    try{const response=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value},body:JSON.stringify(selection())});
      if(!response.ok){let body={};try{body=await response.json();}catch(e){}throw Error(body.error||('No se pudo generar el informe '+label+'.'));}
      const code=response.headers.get('X-ACM-History-Code')||'';const objectUrl=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=objectUrl;a.download=(code||'informe-acm')+extension;a.click();setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);downloaded=true;$('cmp-save').textContent=code?'Guardado · '+code:'Guardado en historial';$('cmp-status').textContent='Informe '+label+' descargado y análisis guardado en el historial.';reportStatus('Informe '+label+' descargado.');
    }catch(error){$('cmp-status').textContent=error.message;reportStatus(error.message);}finally{reportDownloading=false;updateReportButtons();if(downloaded)$('cmp-save').disabled=true;}
  }
  $('cmp-word').addEventListener('click',()=>downloadReport(form.dataset.reportUrl,'.docx','Word'));
  $('cmp-pdf').addEventListener('click',()=>downloadReport(form.dataset.pdfUrl,'.pdf','PDF'));
  $('cmp-html').addEventListener('click',()=>downloadReport(form.dataset.htmlUrl,'.html','HTML'));
  $('cmp-comparison-report').addEventListener('click',()=>setReportMenu($('cmp-comparison-downloads').hidden));
  $('cmp-comparison-report').addEventListener('keydown',event=>{
    if(!['ArrowDown','ArrowUp'].includes(event.key))return;event.preventDefault();setReportMenu(true);
    const items=Array.from($('cmp-comparison-downloads').querySelectorAll('[data-report-format]'));items[event.key==='ArrowUp'?items.length-1:0]?.focus();
  });
  document.addEventListener('click',event=>{if(!event.target.closest('.cmp-comparison-report-footer'))setReportMenu(false);});
  document.addEventListener('keydown',event=>{
    const menu=$('cmp-comparison-downloads');if(menu.hidden)return;
    if(event.key==='Escape'){event.preventDefault();setReportMenu(false);$('cmp-comparison-report').focus();return;}
    const items=Array.from(menu.querySelectorAll('[data-report-format]')),index=items.indexOf(event.target);
    if(index>=0&&['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next].focus();
    }
  });
  $('cmp-comparison-downloads').addEventListener('click',event=>{
    const button=event.target.closest('[data-report-format]');if(!button)return;
    const formats={pdf:[form.dataset.pdfUrl,'.pdf','PDF'],word:[form.dataset.reportUrl,'.docx','Word'],html:[form.dataset.htmlUrl,'.html','HTML']};
    const format=formats[button.dataset.reportFormat];if(format)downloadReport(...format);
  });
  configureType();
  const replicationNode=$('cmp-replication-data');
  if(replicationNode){
    const saved=JSON.parse(replicationNode.textContent),p=saved.params;
    for(const name of ['property_type','age','lat','lng','land','built','rooms','baths','floor','radius','max_radius'])form.elements[name].value=p[name]??'';
    // API/history radii may fall between the slider's ordinary 100 m steps.
    if(p.radius%100!==0){form.elements.radius.step='any';form.elements.radius.value=p.radius;}
    $('cmp-address').value=p.address||'';
    form.querySelectorAll('[name=source]').forEach(source=>{source.disabled=false;});
    configureType();$('cmp-radius-label').textContent=p.radius+' m';
    $('cmp-status').textContent='Datos de '+saved.code+' cargados. Revisa el formulario y pulsa Buscar y calcular.';
  }
  const roleAnalysisNode=$('cmp-role-analysis-data');
  if(roleAnalysisNode){
    const saved=JSON.parse(roleAnalysisNode.textContent);
    if(saved.snapshot){
      snapshot=saved.snapshot;result=snapshot.result;
      const p=snapshot.params;
      for(const name of ['property_type','age','lat','lng','land','built','rooms','baths','floor','radius','max_radius'])if(form.elements[name])form.elements[name].value=p[name]??'';
      if(p.radius%100!==0){form.elements.radius.step='any';form.elements.radius.value=p.radius;}
      $('cmp-address').value=p.address||'';
      configureType();$('cmp-radius-label').textContent=p.radius+' m';
      excluded=new Set(saved.excluded||[]);unselected.clear();(saved.ui?.hidden_ids||[]).forEach(id=>unselected.add(id));
      document.querySelectorAll('[name=map_layer]').forEach(input=>{input.checked=(saved.ui?.layers||[]).includes(input.value);});
      restoredViewport=saved.ui?.viewport||null;
      tab=p.property_type==='Terreno'||result.valuation_mode==='land_only'?'Terreno':'Casa';
      setLocationLocked(true);setSearchFormCollapsed(true);render(false);
      $('cmp-status').textContent='Mismo análisis cargado con los permisos del rol activo.';
    }else if(saved.blocked){
      $('cmp-status').textContent='El análisis se conserva. Este rol no tiene habilitada la consulta de resultados; cambia de vista para volver a verlo.';
    }else{
      $('cmp-status').textContent='El análisis ya no está disponible. Vuelve a buscar para actualizarlo.';
    }
  }
})();
