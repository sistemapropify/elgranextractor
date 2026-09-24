(() => {
  'use strict';
  const $ = id => document.getElementById(id), form=$('cmp-form');
  let snapshot=null,result=null,excluded=new Set(),tab='Casa',map=null,pin=null,circles=[],markers=[],sequence=0,controller=null;
  const money=n=>n==null?'—':new Intl.NumberFormat('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
  const decimals=n=>n==null?'Sin informar':new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(n);
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function input(){return {lat:Number(form.elements.lat.value),lng:Number(form.elements.lng.value),land:Number(form.elements.land.value),built:Number(form.elements.built.value),radius:Number(form.elements.radius.value),max_radius:Number(form.elements.max_radius.value),sources:Array.from(form.querySelectorAll('[name=source]:checked'),x=>x.value)};}
  async function post(path,data){
    if(controller)controller.abort();controller=new AbortController();const current=controller;
    const timer=setTimeout(()=>current.abort(),45000);
    try{const response=await fetch('/acm/pruebas/componentes/'+path+'/',{method:'POST',credentials:'same-origin',signal:current.signal,headers:{'Content-Type':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value},body:JSON.stringify(data)});
      if(!response.headers.get('content-type')?.includes('application/json'))throw Error('El servidor no devolvió datos. Comprueba tu sesión y vuelve a intentar.');
      const body=await response.json();if(!response.ok)throw Error(body.error||'No se pudo completar la consulta.');return body;
    }catch(e){if(e.name==='AbortError')throw Error('La consulta se canceló o superó 45 segundos. Puedes reintentar.');throw e;}finally{clearTimeout(timer);}
  }
  function clearMap(){markers.forEach(m=>m.setMap(null));markers=[];}
  function drawCircles(){
    if(!map)return;circles.forEach(c=>c.setMap(null));circles=[];
    const p=snapshot?.params||input();const center={lat:p.lat,lng:p.lng};if(!Number.isFinite(center.lat)||!Number.isFinite(center.lng))return;
    if(!pin)pin=new google.maps.Marker({map,position:center,title:'Casa objetivo',draggable:true});else pin.setPosition(center);
    if(!pin.cmpListener){pin.addListener('dragend',e=>setLocation(e.latLng.lat(),e.latLng.lng()));pin.cmpListener=true;}
    circles.push(new google.maps.Circle({map,center,radius:p.radius,strokeColor:'#4597ec',strokeWeight:2,fillColor:'#4597ec',fillOpacity:.08}));
    if(result?.land_radius>p.radius)circles.push(new google.maps.Circle({map,center,radius:result.land_radius,strokeColor:'#e8b455',strokeWeight:2,fillOpacity:0}));
  }
  function invalidate(){sequence++;if(controller)controller.abort();snapshot=null;result=null;excluded.clear();clearMap();$('cmp-export').disabled=true;$('cmp-cards').innerHTML='<p class="cmp-muted">Busca nuevamente para aplicar los parámetros.</p>';$('cmp-counts').textContent='Sin comparables';$('cmp-new').innerHTML='<h2>Resultado nuevo</h2><p>Parámetros modificados: vuelve a buscar.</p>';$('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>—</strong>';$('cmp-warnings').replaceChildren();$('cmp-status').textContent='Listo para una nueva búsqueda.';$('cmp-search').disabled=false;drawCircles();}
  function setLocation(lat,lng){form.elements.lat.value=lat.toFixed(7);form.elements.lng.value=lng.toFixed(7);invalidate();if(map)map.panTo({lat,lng});}
  window.initComponentMap=()=>{
    const p=input();map=new google.maps.Map($('cmp-map'),{center:{lat:p.lat,lng:p.lng},zoom:15,mapTypeControl:false,streetViewControl:false});map.addListener('click',e=>setLocation(e.latLng.lat(),e.latLng.lng()));
    const auto=new google.maps.places.Autocomplete($('cmp-address'),{fields:['geometry','formatted_address'],componentRestrictions:{country:'pe'}});
    auto.addListener('place_changed',()=>{const place=auto.getPlace();if(place.geometry){setLocation(place.geometry.location.lat(),place.geometry.location.lng());map.setZoom(16);}});drawCircles();
  };
  window.gm_authFailure=()=>{$('cmp-status').textContent='No se pudo cargar Google Maps. Puedes ingresar latitud y longitud para buscar.';};
  function visibleRows(){return snapshot.records.filter(r=>r.kind==='Casa'||r.distance<=result.land_radius);}
  function renderMap(){
    if(!map)return;clearMap();drawCircles();
    visibleRows().forEach(r=>{const marker=new google.maps.Marker({map,position:{lat:r.lat,lng:r.lng},title:r.title,opacity:(r.issues.length || excluded.has(r.id)) ? .55 : 1,icon:{path:google.maps.SymbolPath.CIRCLE,scale:6,fillColor:r.issues.length?'#98a4b4':r.kind==='Terreno'?'#d6a548':'#3789dd',fillOpacity:1,strokeColor:'#ffffff',strokeWeight:1}});
      marker.addListener('click',()=>{tab=r.issues.length?'reference':r.kind;renderCards();const card=document.querySelector('[data-record="'+CSS.escape(r.id)+'"]');card?.scrollIntoView({behavior:'smooth',block:'nearest'});});markers.push(marker);});
  }
  function renderSummary(){
    const r=result,n=r.new;
    $('cmp-warnings').innerHTML=snapshot.warnings.map(w=>'<div class="cmp-warning">'+escape(w)+'</div>').join('');
    $('cmp-new').innerHTML='<h2>Resultado nuevo · por componentes</h2>'+
      '<p class="cmp-muted">'+r.land_count+' terrenos · '+r.house_count+' casas completas · suelo hasta '+r.land_radius+' m</p>'+
      (r.land_unit!=null?'<div class="cmp-line"><span>Referencia del suelo</span><strong>'+money(r.land_unit)+'/m²</strong></div>':'')+
      (n?'<div class="cmp-line"><span>Terreno objetivo</span><strong>'+money(n.land_value)+'</strong></div><div class="cmp-line"><span>Construcción y mejoras</span><strong>'+money(n.built_value)+'</strong></div><div class="cmp-total">'+money(n.total)+'</div><p class="cmp-muted">Aporte de mejoras: '+money(n.built_unit)+'/m² construido.<br>Rango central orientativo: '+money(n.range_low)+' – '+money(n.range_high)+'. No es un intervalo de confianza.</p><div class="cmp-difference">Diferencia frente al anterior: '+(n.delta>=0?'+':'')+money(n.delta)+' ('+(n.delta_pct>=0?'+':'')+decimals(n.delta_pct)+'%)</div>':'<p class="cmp-warning">'+r.messages.map(escape).join('<br>')+'</p>');
    $('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>'+money(r.old?.total)+'</strong><small>'+(r.old?money(r.old.unit)+'/m² construido<br>':'')+'Mismas casas completas seleccionadas. Promedio ponderado por distancia; es una referencia, no una validación del nuevo resultado.</small>';
  }
  function renderCards(){
    const rows=visibleRows();const houses=rows.filter(r=>r.kind==='Casa'&&!r.issues.length),lands=rows.filter(r=>r.kind==='Terreno'&&!r.issues.length),refs=rows.filter(r=>r.issues.length);
    $('cmp-house-count').textContent=houses.length;$('cmp-land-count').textContent=lands.length;$('cmp-ref-count').textContent=refs.length;
    $('cmp-counts').textContent=rows.length+' encontrados · '+houses.length+' casas aptas · '+lands.length+' terrenos aptos · '+refs.length+' referencias';
    document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
    const selected=tab==='reference'?refs:tab==='Casa'?houses:lands;
    const breakdown=new Map(result.breakdown.map(r=>[r.id,r]));
    $('cmp-cards').innerHTML=selected.map(r=>{const b=breakdown.get(r.id);return '<article class="cmp-card" data-record="'+escape(r.id)+'"><div class="cmp-card-top">'+(r.image?'<img src="'+escape(r.image)+'" loading="lazy" alt="Foto del anuncio">':'')+'<div class="cmp-card-main"><div class="cmp-card-sub">'+escape(r.source)+' · '+escape(r.code)+' · '+Math.round(r.distance)+' m</div><div class="cmp-card-title">'+escape(r.title)+'</div><div class="cmp-card-price">'+money(r.price)+'</div><span class="cmp-badge '+(r.issues.length?'ref':'')+'">'+(r.issues.length?'Solo referencia':r.kind==='Casa'?'Casa apta':'Terreno apto')+'</span></div>'+(!r.issues.length?'<label><input type="checkbox" data-include="'+escape(r.id)+'" '+(!excluded.has(r.id)?'checked':'')+'> Incluir</label>':'')+'</div><div class="cmp-card-areas"><span>Terreno: <strong>'+decimals(r.land)+(r.land?' m²':'')+'</strong></span><span>Construcción: <strong>'+decimals(r.built)+(r.built?' m²':'')+'</strong></span></div><div class="cmp-card-sub">'+escape(r.district)+' · Ubicación '+escape(r.precision)+(r.converted?' · Precio convertido de soles':'')+(r.distance>snapshot.params.radius?' · Área ampliada de terrenos':'')+'</div>'+(r.issues.length?'<div class="cmp-issues">'+r.issues.map(escape).join(' · ')+'</div>':'')+(r.kind==='Terreno'&&r.land&&r.price?'<div class="cmp-breakdown">Oferta de suelo: '+money(r.price/r.land)+'/m²</div>':'')+(b?'<div class="cmp-breakdown">Suelo estimado: '+money(b.land_value)+'<br>Remanente de construcción y mejoras: '+money(b.remainder)+' · '+money(b.built_unit)+'/m²'+(!b.usable?'<br><span class="cmp-issues">Requiere revisión: el suelo estimado absorbe el precio.</span>':'')+'</div>':'')+(r.url?'<a href="'+escape(r.url)+'" target="_blank" rel="noopener noreferrer">Abrir publicación ↗</a>':'')+'</article>';}).join('')||'<p class="cmp-muted">No hay registros en este grupo. Puedes revisar los otros grupos o ajustar la búsqueda.</p>';
    $('cmp-cards').querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.remove();},{once:true}));
  }
  function render(){renderSummary();renderCards();renderMap();$('cmp-export').disabled=false;}
  form.addEventListener('submit',async e=>{e.preventDefault();const p=input();if(!p.sources.length){$('cmp-status').textContent='Selecciona al menos una fuente.';return;}const seq=++sequence;$('cmp-search').disabled=true;$('cmp-export').disabled=true;$('cmp-status').textContent='Buscando casas y terrenos…';
    try{const data=await post('buscar',p);if(seq!==sequence)return;snapshot=data;result=data.result;excluded.clear();tab='Casa';render();$('cmp-status').textContent='Búsqueda terminada. Puedes desmarcar comparables para recalcular.';}catch(error){if(seq===sequence){snapshot=null;result=null;clearMap();$('cmp-status').textContent=error.message;$('cmp-new').innerHTML='<h2>Resultado no disponible</h2><p>La búsqueda no terminó. Reintenta.</p>';$('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>—</strong>';$('cmp-cards').replaceChildren();}}finally{if(seq===sequence)$('cmp-search').disabled=false;}});
  form.addEventListener('input',e=>{if(e.target.name){$('cmp-radius-label').textContent=form.elements.radius.value+' m';invalidate();}});
  form.addEventListener('change',e=>{if(e.target.name)invalidate();});
  $('cmp-address').addEventListener('keydown',e=>{if(e.key==='Enter')e.preventDefault();});
  document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{tab=button.dataset.tab;if(snapshot)renderCards();}));
  $('cmp-cards').addEventListener('change',async e=>{const id=e.target.dataset.include;if(!id||!snapshot)return;e.target.checked?excluded.delete(id):excluded.add(id);const seq=++sequence;$('cmp-status').textContent='Recalculando ambos métodos…';$('cmp-export').disabled=true;
    try{const data=await post('calcular',{token:snapshot.token,excluded:[...excluded]});if(seq!==sequence)return;result=data.result;render();$('cmp-status').textContent='Resultados actualizados con tu selección.';}catch(error){if(seq===sequence){$('cmp-status').textContent=error.message;$('cmp-new').innerHTML='<h2>Resultado desactualizado</h2><p>No se pudo aplicar la selección. Busca nuevamente.</p>';$('cmp-old').innerHTML='<span>Cálculo anterior</span><strong>—</strong>';}}});
  $('cmp-export').addEventListener('click',()=>{if(!snapshot||!result)return;const file={fecha:new Date().toISOString(),parametros:snapshot.params,advertencias:snapshot.warnings,excluidos:[...excluded],resultado:result,comparables:visibleRows()};const url=URL.createObjectURL(new Blob([JSON.stringify(file,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='acm-componentes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
})();
