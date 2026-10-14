(() => {
  'use strict';
  const groups = [
    {key:'police',label:'Comisaría',types:['police']},
    {key:'health',label:'Posta u hospital',types:['hospital','medical_center','medical_clinic']},
    {key:'mall',label:'Mall o centro comercial',types:['shopping_mall']},
    {key:'school',label:'Colegio',types:['school','primary_school','secondary_school']}
  ];
  const point = value => {
    const rawLat = typeof value?.lat === 'function' ? value.lat() : value?.lat;
    const rawLng = typeof value?.lng === 'function' ? value.lng() : value?.lng;
    if(rawLat==null || rawLng==null || rawLat==='' || rawLng==='')return null;
    const lat = Number(rawLat), lng = Number(rawLng);
    return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat)<=90 && Math.abs(lng)<=180 ? {lat,lng} : null;
  };
  function proximity(meters) {
    if (!Number.isFinite(meters) || meters < 0) return 'unknown';
    return meters<=300 ? 'blue' : meters<=1000 ? 'yellow' : 'red';
  }
  function metric(item) {
    if (!item || item.condition !== 'ROUTE_EXISTS' || item.error ||
        !Number.isFinite(item.distanceMeters) || item.distanceMeters<0 ||
        !Number.isFinite(item.durationMillis) || item.durationMillis<0) return null;
    return {meters:item.distanceMeters,minutes:Math.ceil(item.durationMillis/60000)};
  }
  function closest(rows,mode) {
    const routes=rows.filter(row=>row[mode]);
    return [...(routes.length ? routes : rows)].sort((a,b)=>
      (routes.length ? a[mode].meters-b[mode].meters : a.direct-b.direct) || String(a.id).localeCompare(String(b.id)))[0] || null;
  }
  function straight(a,b) {
    const rad=x=>x*Math.PI/180,dlat=rad(b.lat-a.lat),dlng=rad(b.lng-a.lng);
    const h=Math.sin(dlat/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(b.lat))*Math.sin(dlng/2)**2;
    return 12742000*Math.asin(Math.min(1,Math.sqrt(h)));
  }
  const distance=n=>n<1000 ? Math.round(n).toLocaleString('es-PE')+' m' : (n/1000).toLocaleString('es-PE',{maximumFractionDigits:2})+' km';
  function element(tag,text,css) {
    const el=document.createElement(tag);if(text!=null)el.textContent=text;if(css)el.className=css;return el;
  }
  function friendly(error,service) {
    const code=String(error?.code||error?.message||error||'').toUpperCase();
    if (/DENIED|PERMISSION|AUTH|API_KEY|BILLING|NOT ENABLED|NOT ACTIVATED/.test(code))
      return 'Google no autorizó '+service+'. Revisa que la API esté habilitada, la facturación y los permisos de la clave.';
    if (/QUOTA|RESOURCE_EXHAUSTED|OVER_QUERY_LIMIT/.test(code)) return 'Google alcanzó el límite de consultas. Intenta actualizar más tarde.';
    if (/TIMEOUT/.test(code)) return 'Google tardó demasiado en responder. Vuelve a pulsar Buscar y calcular.';
    return 'No se pudo consultar '+service+' en Google. Vuelve a pulsar Buscar y calcular.';
  }
  async function bounded(promise) {
    let timer;
    try {return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('TIMEOUT')),20000);})]);}
    finally {clearTimeout(timer);}
  }
  function init(map) {
    const $=id=>document.getElementById(id),card=$('cmp-nearby');
    if (!card || map.__acmNearby) return;
    map.__acmNearby=true;
    const status=$('cmp-nearby-status'),list=$('cmp-nearby-list'),radius=$('cmp-nearby-radius'),sort=$('cmp-nearby-sort');
    const cache=new Map();let origin=null,serial=0,routeSerial=0,timer=null,data=null,markers=[],polylines=[];
    let placesLibrary=null,routesLibrary=null;
    const lib=type=>type==='places' ? (placesLibrary ||= google.maps.importLibrary('places').catch(error=>{placesLibrary=null;throw error;})) :
      (routesLibrary ||= google.maps.importLibrary('routes').catch(error=>{routesLibrary=null;throw error;}));
    const clearRoute=()=>{++routeSerial;polylines.forEach(line=>line.setMap(null));polylines=[];$('cmp-nearby-route').hidden=true;$('cmp-nearby-warnings').replaceChildren();};
    const clearMarkers=()=>{markers.forEach(marker=>marker.setMap(null));markers=[];};
    function setOpen(open) {
      $('cmp-nearby-content').hidden=!open;
      const toggle=$('cmp-nearby-toggle');toggle.setAttribute('aria-expanded',String(open));
      toggle.setAttribute('aria-label',(open?'Minimizar':'Expandir')+' lugares cercanos');toggle.textContent=open?'−':'+';
    }
    const expand=()=>{card.hidden=false;setOpen(true);};
    async function showRoute(row,mode) {
      if (!origin || !row[mode]) return;
      clearRoute();const version=routeSerial,targetVersion=serial,start={...origin};
      const routeStatus=$('cmp-nearby-route');routeStatus.hidden=false;routeStatus.textContent='Trazando recorrido…';
      try {
        const {Route}=await bounded(lib('routes'));
        const response=await bounded(Route.computeRoutes({origin:start,destination:row.place,travelMode:mode,
          ...(mode==='DRIVING'?{routingPreference:'TRAFFIC_AWARE'}:{}),fields:['path','distanceMeters','durationMillis','warnings'],language:'es',region:'pe'}));
        if (version!==routeSerial || targetVersion!==serial) return;
        const route=response.routes?.[0],value=metric({condition:'ROUTE_EXISTS',distanceMeters:route?.distanceMeters,durationMillis:route?.durationMillis});
        if(!Array.isArray(route?.path) || !route.path.length || !route.path.every(point) || !value)throw Error('No route');
        polylines=[new google.maps.Polyline({map,path:route.path,strokeColor:'#3b82f6',strokeWeight:5,strokeOpacity:.95,zIndex:140000,clickable:false})];
        routeStatus.textContent=row.name+' · '+(mode==='WALKING'?'A pie':'En auto')+' · '+distance(value.meters)+' · '+value.minutes+' min estimados';
        (route.warnings||[]).forEach(warning=>$('cmp-nearby-warnings').append(element('p',warning)));
        const bounds=new google.maps.LatLngBounds();route.path.forEach(p=>bounds.extend(p));map.fitBounds(bounds,{top:45,left:Math.min(card.offsetWidth+30,Math.round(map.getDiv().clientWidth*.4)),bottom:90,right:60});
      } catch(error) {if(version===routeSerial && targetVersion===serial)routeStatus.textContent=friendly(error,'la ruta');}
    }
    function render() {
      clearMarkers();list.replaceChildren();if(!data)return;
      const mode=sort.value;
      for (const group of data.groups) {
        const row=closest(group.rows,mode),box=element('article',null,'cmp-nearby-item');
        box.append(element('h3',group.label));
        if(!row){box.append(element('p',group.error||'Google no encontró lugares de esta categoría en el radio elegido.','cmp-nearby-empty'));list.append(box);continue;}
        box.dataset.level=proximity(row[mode]?.meters);
        box.append(element('strong',row.name,'cmp-nearby-name'));
        if(row.address)box.append(element('p',row.address,'cmp-nearby-address'));
        for(const [key,label] of [['WALKING','A pie'],['DRIVING','En auto']]) {
          const line=element('div',null,'cmp-nearby-metric'),value=row[key];
          line.append(element('span',label),element('strong',value ? distance(value.meters)+' · '+value.minutes+' min' : 'Sin recorrido disponible'));
          if(value){const button=element('button','Ver ruta');button.type='button';button.setAttribute('aria-label','Ver ruta '+label.toLowerCase()+' a '+row.name);button.addEventListener('click',()=>showRoute(row,key));line.append(button);}
          box.append(line);
        }
        if(!row[mode])box.append(element('p',distance(row.direct)+' en línea recta · cercanía por recorrido no disponible','cmp-nearby-empty'));
        box.append(element('small',!row[mode] ? 'Más cercano por distancia en línea recta' : mode==='DRIVING' ? 'Más cercano por recorrido en auto' : 'Más cercano por recorrido a pie'));
        const link=element('a','Ver lugar en Google Maps ↗');link.href='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(row.name)+'&query_place_id='+encodeURIComponent(row.id);link.target='_blank';link.rel='noopener noreferrer';box.append(link);
        const marker=new google.maps.Marker({map,position:row.position,title:group.label+': '+row.name,
          icon:{path:google.maps.SymbolPath.CIRCLE,scale:8,fillColor:{blue:'#3b82f6',yellow:'#e9bd26',red:'#ed6363',unknown:'#94a3b8'}[box.dataset.level],fillOpacity:1,strokeColor:'#ffffff',strokeWeight:2},zIndex:130000});
        marker.addListener('click',()=>{expand();box.scrollIntoView({block:'nearest'});});markers.push(marker);list.append(box);
      }
      $('cmp-nearby-updated').textContent='Google Maps · '+new Date(data.time).toLocaleTimeString('es-PE',{hour:'2-digit',minute:'2-digit'})+' · tiempos estimados';
      status.textContent=data.errors.join(' ');
    }
    async function load(force=false) {
      if(!origin)return;const version=++serial,start={...origin},range=Number(radius.value),key=start.lat.toFixed(7)+','+start.lng.toFixed(7)+':'+range;
      clearRoute();clearMarkers();data=null;list.replaceChildren();$('cmp-nearby-updated').textContent='';card.setAttribute('aria-busy','false');
      if($('cmp-form').dataset.authenticated==='false'){status.textContent='Inicia sesión en PROMETEO para consultar los lugares cercanos.';return;}
      const saved=cache.get(key);if(!force && saved && Date.now()-saved.time<180000){data=saved;render();return;}
      card.setAttribute('aria-busy','true');status.textContent='Buscando los lugares más cercanos…';
      try {
        const {Place,SearchNearbyRankPreference}=await bounded(lib('places'));if(version!==serial)return;
        const answers=await Promise.allSettled(groups.map(group=>bounded(Place.searchNearby({fields:['id','displayName','location','formattedAddress'],
          locationRestriction:{center:start,radius:range},includedPrimaryTypes:group.types,maxResultCount:5,
          rankPreference:SearchNearbyRankPreference.DISTANCE,language:'es',region:'pe'}))));
        if(version!==serial)return;
        const found=groups.map((group,i)=>({...group,error:answers[i].status==='rejected'?friendly(answers[i].reason,'los lugares cercanos'):null,
          rows:answers[i].status==='fulfilled'?(answers[i].value.places||[]).slice(0,5).filter(p=>p.id && point(p.location)).map(p=>({id:p.id,name:p.displayName||group.label,address:p.formattedAddress||'',position:point(p.location),place:p,direct:straight(start,point(p.location))})):[]}));
        const all=[...new Map(found.flatMap(g=>g.rows).map(row=>[row.id,row])).values()];
        const errors=[];
        if(all.length) {
          status.textContent='Calculando distancias y tiempos de recorrido…';
          try {
            const {RouteMatrix}=await bounded(lib('routes'));if(version!==serial)return;
            const metrics=await Promise.allSettled(['WALKING','DRIVING'].map(mode=>bounded(RouteMatrix.computeRouteMatrix({origins:[start],destinations:all.map(row=>row.place),travelMode:mode,
              ...(mode==='DRIVING'?{routingPreference:'TRAFFIC_AWARE'}:{}),fields:['distanceMeters','durationMillis','condition'],language:'es',region:'pe'}))));
            if(version!==serial)return;
            metrics.forEach((answer,i)=>{const mode=['WALKING','DRIVING'][i];if(answer.status==='rejected'){errors.push(friendly(answer.reason,mode==='WALKING'?'las rutas a pie':'las rutas en auto'));return;}
              all.forEach((row,index)=>{row[mode]=metric(answer.value.matrix?.rows?.[0]?.items?.[index]);});});
            found.forEach(group=>group.rows.forEach(row=>{const calculated=all.find(r=>r.id===row.id);row.WALKING=calculated.WALKING;row.DRIVING=calculated.DRIVING;}));
          } catch(error) {if(version!==serial)return;errors.push(friendly(error,'los recorridos'));}
        }
        data={groups:found,errors:[...new Set(errors)],time:Date.now()};
        if(!errors.length && !found.some(group=>group.error)){cache.set(key,data);if(cache.size>8)cache.delete(cache.keys().next().value);}
        render();
      } catch(error) {if(version===serial)status.textContent=friendly(error,'los lugares cercanos');}
      finally {if(version===serial)card.setAttribute('aria-busy','false');}
    }
    function update(value) {
      const next=point(value);if(!next)return;
      const unchanged=origin && Math.abs(origin.lat-next.lat)<1e-7 && Math.abs(origin.lng-next.lng)<1e-7;
      if(unchanged)return;
      origin=next;card.hidden=true;setOpen(false);
      ++serial;clearTimeout(timer);clearRoute();clearMarkers();data=null;list.replaceChildren();card.setAttribute('aria-busy','false');
      $('cmp-nearby-origin').textContent='Desde el pin: '+origin.lat.toFixed(5)+', '+origin.lng.toFixed(5);
      status.textContent='Pulsa Buscar y calcular para consultar los lugares de esta ubicación.';
    }
    document.addEventListener('acm:target-location',event=>update(event.detail));
    document.addEventListener('acm:search-completed',event=>{
      update(event.detail);if(!origin)return;card.hidden=false;setOpen(false);return load();
    });
    radius.addEventListener('change',()=>{++serial;clearRoute();clearMarkers();data=null;list.replaceChildren();card.setAttribute('aria-busy','false');status.textContent='Radio cambiado. Pulsa Buscar y calcular para consultar nuevamente.';});
    sort.addEventListener('change',()=>{clearRoute();render();});
    $('cmp-nearby-toggle').addEventListener('click',()=>setOpen($('cmp-nearby-content').hidden));
    $('cmp-nearby-clear-route').addEventListener('click',clearRoute);
    $('cmp-nearby-close').addEventListener('click',()=>{++serial;clearTimeout(timer);clearRoute();clearMarkers();data=null;origin=null;card.hidden=true;card.setAttribute('aria-busy','false');});
    if($('cmp-replication-data')){const form=$('cmp-form');update({lat:form.elements.lat.value,lng:form.elements.lng.value});}
  }
  window.ACMNearby={init,point,proximity,metric,closest,straight};
})();
