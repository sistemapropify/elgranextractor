(() => {
'use strict';
const $=id=>document.getElementById(id),ns='http://www.w3.org/2000/svg',layers=new Map();
let map=null,data=null,meta=null,job=null,serial=0,timer=null,box=[0,0,100,100],drag=null,moved=false,measure=null,points=[],measurement=null;
let importStarted=0,importClock=null;
const geographic=()=>$('planos-crs').value!=='unknown';
const format=n=>new Intl.NumberFormat('es-PE',{maximumFractionDigits:2}).format(n);
function status(text,error=false){$('planos-status').textContent=text;$('planos-status').dataset.error=String(error);}
function importState(phase,detail,filename){
 const busy=['uploading','reading','drawing'].includes(phase),titles={idle:'Ningún archivo seleccionado',uploading:'1 de 3 · Subiendo DWG',reading:'2 de 3 · Leyendo el DWG',drawing:'3 de 3 · Dibujando la capa',completed:'Plano listo',failed:'No se pudo completar la lectura',disconnected:'No se pudo consultar el estado'};
 $('planos-import-state').dataset.state=phase;$('planos-import-state').setAttribute('aria-busy',String(busy));$('planos-import-title').textContent=titles[phase];$('planos-import-detail').textContent=detail;
 if(filename){$('planos-import-file').textContent=filename;$('planos-import-file').hidden=false;}
 $('planos-import-progress').hidden=!busy;$('planos-file').disabled=busy;$('planos-import-retry').hidden=phase!=='disconnected'||!job;
 if(busy&&!importStarted)importStarted=Date.now();
 function elapsed(){const seconds=Math.floor((Date.now()-importStarted)/1000);$('planos-import-elapsed').textContent='Tiempo transcurrido: '+Math.floor(seconds/60)+' min '+String(seconds%60).padStart(2,'0')+' s';}
 if(importStarted){elapsed();$('planos-import-elapsed').hidden=false;}
 if(busy&&!importClock)importClock=setInterval(elapsed,1000);
 if(!busy&&importClock){clearInterval(importClock);importClock=null;}
 if(phase==='idle'){importStarted=0;$('planos-import-elapsed').hidden=true;$('planos-import-file').hidden=true;}
}
function positions(g){const list=[];function walk(v){if(typeof v[0]==='number')list.push(v);else v.forEach(walk);}walk(g.coordinates);return list;}
function visible(){return [...layers.values()].filter(l=>l.visible).flatMap(l=>l.features);}
function controls(){const has=!!visible().length;['planos-all','planos-none','planos-layer-search'].forEach(id=>$(id).disabled=!meta);$('planos-fit').disabled=!has;$('planos-export').disabled=!has||!geographic();['planos-distance','planos-area'].forEach(id=>$(id).disabled=!geographic()||!map);}
async function api(path){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);try{const r=await fetch('/catastro/api/planos/'+path,{credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json'}});if(!r.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para leer el plano.');const v=await r.json();if(!r.ok)throw Error(v.error||'No se pudo leer el plano.');return v;}catch(error){if(error.name==='AbortError')throw Error('El servidor no respondió en 20 segundos. Puedes volver a consultar el estado sin subir otra vez el DWG.');throw error;}finally{clearTimeout(timeout);}}
function setBox(v){box=v;$('planos-cad').setAttribute('viewBox',v.join(' '));}
function fit(){
 const features=visible();if(!features.length)return;
 if(geographic()){if(!map)return;const b=new google.maps.LatLngBounds();features.forEach(f=>positions(f.geometry).forEach(([lng,lat])=>b.extend({lat,lng})));map.fitBounds(b,{left:$('planos-panels').hidden?30:Math.min(310,$('planos-map').clientWidth*.4),right:40,top:35,bottom:60});}
 else {let x=Infinity,y=Infinity,X=-Infinity,Y=-Infinity;features.forEach(f=>positions(f.geometry).forEach(p=>{x=Math.min(x,p[0]);X=Math.max(X,p[0]);y=Math.min(y,p[1]);Y=Math.max(Y,p[1]);}));const w=Math.max(X-x,1),h=Math.max(Y-y,1);setBox([x-w*($('planos-panels').hidden ? .12 : .55),-Y-h*.12,w*($('planos-panels').hidden?1.24:1.8),h*1.24]);}
}
function inspect(feature){
 const properties=$('planos-selected-properties');properties.replaceChildren();
 function field(name,value){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=String(value);properties.append(dt,dd);}
 field('Geometría',feature.geometry.type);
 if(feature.geometry.type.includes('Polygon')){const polygons=feature.geometry.type==='Polygon'?[feature.geometry.coordinates]:feature.geometry.coordinates;let area=0;
  polygons.forEach(rings=>rings.forEach((ring,index)=>{const value=geographic()&&map?Math.abs(google.maps.geometry.spherical.computeArea(ring.map(([lng,lat])=>({lat,lng})))):Math.abs(ring.slice(1).reduce((sum,p,i)=>sum+ring[i][0]*p[1]-p[0]*ring[i][1],0))/2;area+=(index===0?1:-1)*value;}));
  const unit=geographic()?'m':({4:'mm',5:'cm',6:'m',7:'km'}[meta?.units]||'unidades del plano');
  field('Área geométrica'+(geographic()?' aproximada':''),format(area)+' '+unit+'²');
 }
 Object.entries(feature.properties).filter(([key])=>!['color'].includes(key)).forEach(([key,value])=>{if(value)field(key,value);});
 $('planos-selected-layer').textContent=feature.properties.capa;$('planos-selection-empty').hidden=true;$('planos-selection-data').hidden=false;$('planos-selection').open=true;
}
function draw(){
 data?.setMap(null);data=null;const svg=$('planos-cad'),host=$('planos-cad-entities'),features=visible(),opacity=Number($('planos-opacity').value)/100;host.replaceChildren();
 svg.toggleAttribute('hidden',geographic()||!meta);$('planos-map').hidden=!geographic()&&!!meta;$('planos-coordinates').textContent=!geographic()&&meta?'Coordenadas originales del plano · vista CAD':'WGS84 · longitud / latitud';
 $('planos-cad-notice').hidden=geographic()||!meta;
 if(geographic()&&map){data=new google.maps.Data({map});data.addGeoJson({type:'FeatureCollection',features});data.setStyle(f=>{const c=layers.get(f.getProperty('capa')).color;return {fillColor:c,strokeColor:c,fillOpacity:opacity,strokeWeight:1.5,icon:{path:google.maps.SymbolPath.CIRCLE,scale:4,fillColor:c,fillOpacity:1,strokeColor:c}};});data.addListener('click',event=>{if(measure)addMeasurement(event.latLng);else {const f=features.find(item=>item.id===event.feature.getId());if(f)inspect(f);}});}
 else if(!geographic()&&meta){const span=Math.max((meta.bounds?.[2]||1)-(meta.bounds?.[0]||0),1);
  features.forEach(feature=>{const g=feature.geometry,c=layers.get(feature.properties.capa).color;let node;
   if(g.type==='Point'){const [x,y]=g.coordinates;node=document.createElementNS(ns,feature.properties.texto?'text':'circle');if(feature.properties.texto){node.setAttribute('x',x);node.setAttribute('y',-y);node.setAttribute('font-size',Math.max(span/500,.01));node.textContent=feature.properties.texto;}else {node.setAttribute('cx',x);node.setAttribute('cy',-y);node.setAttribute('r',Math.max(span/1500,.005));}node.setAttribute('fill',c);}
   else {node=document.createElementNS(ns,'path');const rings=g.type==='Polygon'?g.coordinates:g.type==='MultiPolygon'?g.coordinates.flat():[g.coordinates];node.setAttribute('d',rings.map(ring=>ring.map(([x,y],i)=>(i?'L':'M')+x+' '+(-y)).join(' ')+(g.type.includes('Polygon')?' Z':'')).join(' '));node.setAttribute('fill',g.type.includes('Polygon')?c:'none');node.setAttribute('fill-opacity',opacity);node.setAttribute('fill-rule','evenodd');node.setAttribute('stroke',c);node.setAttribute('stroke-width','1.3');}
   node.addEventListener('click',event=>{event.stopPropagation();if(!moved)inspect(feature);});host.append(node);
  });
 }controls();
}
function renderLayers(){
 const host=$('planos-layers'),filter=$('planos-layer-search').value.toLocaleLowerCase();host.replaceChildren();let i=0;
 for(const [name,row] of layers){const line=document.createElement('div'),check=document.createElement('input'),label=document.createElement('label'),count=document.createElement('small'),color=document.createElement('input');line.className='planos-layer';line.hidden=!name.toLocaleLowerCase().includes(filter);check.type='checkbox';check.checked=row.visible;check.disabled=!row.drawable||row.loading;check.id='plano-layer-'+i++;label.htmlFor=check.id;label.textContent=name;count.textContent=row.count+' entidades · '+row.drawable+' dibujables'+(row.visible?' · '+row.features.length+' cargadas':'');label.append(count);color.type='color';color.value=row.color;color.setAttribute('aria-label','Color de '+name);
  check.addEventListener('change',async()=>{row.visible=check.checked;if(row.visible&&!row.loaded)await load(name,true);else draw();renderLayers();});color.addEventListener('input',()=>{row.color=color.value;draw();});line.append(check,label,color);
  if(row.loaded&&row.next!==null){const more=document.createElement('button');more.type='button';more.className='planos-button planos-small planos-more';more.textContent=row.loading?'Cargando…':'Cargar más entidades';more.disabled=row.loading;more.addEventListener('click',()=>load(name));line.append(more);}
  host.append(line);
 }$('planos-layer-count').textContent=layers.size;
}
async function load(name,center=false){
 const row=layers.get(name);if(!row||row.loading||!row.drawable||row.loaded&&row.next===null)return;
 const stamp=serial,id=job;row.loading=true;renderLayers();
 try {const v=await api(id+'/capa/?'+new URLSearchParams({layer:name,offset:row.next||0,crs:$('planos-crs').value}));if(stamp!==serial)return;row.features.push(...v.features);row.loaded=true;row.next=v.next_offset;draw();if(center)fit();status('Capa «'+name+'»: '+row.features.length+' de '+row.drawable+' entidades dibujables cargadas.');return true;}
 catch(error){if(stamp===serial){row.visible=false;status(error.message,true);}}
 finally {if(stamp===serial){row.loading=false;renderLayers();}}
}
async function ready(value){
 meta=value;layers.clear();value.layers.forEach(row=>layers.set(row.name,{...row,color:/^#[0-9a-f]{6}$/i.test(row.color)?row.color:'#71d5b2',features:[],visible:false,next:0,loaded:false,loading:false}));
 $('planos-file-info').hidden=false;$('planos-file-name').textContent=value.filename;$('planos-file-count').textContent=format(value.bytes/1048576)+' MB · '+value.entities+' entidades · '+layers.size+' capas';
 $('planos-map-caption').textContent=value.filename+' · '+(geographic()?'sistema seleccionado':'coordenadas CAD sin ubicación confirmada');
 const omitted=Object.entries(value.unsupported||{}).map(([key,count])=>key+': '+count).join(' · ');$('planos-cad-warnings').hidden=!omitted;$('planos-cad-warnings').textContent=omitted?'Entidades conservadas en el original que este visor no dibuja: '+omitted:'';
 renderLayers();draw();
 const geometryCount=row=>['LWPOLYLINE','POLYLINE','HATCH','SOLID'].reduce((n,type)=>n+(row.types[type]||0),0),rows=[...layers.values()].filter(row=>row.drawable);
 const cadastral=rows.filter(row=>/^(lotes?|parcelas?|predios?)(?:$|[ _-])/i.test(row.name)&&geometryCount(row)>(row.types.TEXT||0)+(row.types.MTEXT||0));
 const first=cadastral.sort((a,b)=>geometryCount(b)-geometryCount(a))[0]||rows.sort((a,b)=>geometryCount(b)-geometryCount(a))[0];
 if(first){first.visible=true;importState('drawing','El archivo ya se leyó. Preparando la capa «'+first.name+'»…',value.filename);if(await load(first.name,true))importState('completed',layers.size+' capas disponibles · «'+first.name+'»: '+first.features.length+' de '+first.drawable+' entidades cargadas.'+(geographic()?'':' Vista CAD: coordenadas sin confirmar.'));else importState('failed','El DWG se leyó, pero no se pudo dibujar la primera capa. '+$('planos-status').textContent);}
 else {status('DWG leído. No contiene entidades compatibles para dibujar.',true);importState('completed','El DWG se leyó. No contiene entidades compatibles para dibujar.',value.filename);}
}
async function poll(id){
 const stamp=serial;
 importState('reading','Consultando el avance del archivo en el servidor…');$('planos-import-progress').removeAttribute('value');
 try {const v=await api(id+'/');if(stamp!==serial)return;status(v.message||'DWG recibido.',v.status==='failed');if(v.status==='completed'){await ready(v);return;}if(v.status==='failed'){importState('failed',v.message,v.filename);return;}importState('reading',v.message||'Preparando lectura de capas.',v.filename);timer=setTimeout(()=>poll(id),2000);}
 catch(error){if(stamp===serial){status(error.message,true);importState('disconnected',error.message);}}
}
function reset(){importState('idle','Abre un DWG para comenzar la lectura.');$('planos-cad-notice').hidden=true;serial++;clearTimeout(timer);$('planos-crs').value='unknown';measure=null;['distance','area'].forEach(key=>$('planos-'+key).setAttribute('aria-pressed','false'));map?.setOptions({draggableCursor:null});data?.setMap(null);data=null;job=null;meta=null;layers.clear();$('planos-cad-entities').replaceChildren();$('planos-cad').setAttribute('hidden','');$('planos-map').hidden=false;$('planos-file-info').hidden=true;$('planos-selection-data').hidden=true;$('planos-selection-empty').hidden=false;$('planos-cad-warnings').hidden=true;$('planos-layers').replaceChildren();$('planos-layer-count').textContent='0';$('planos-file').value='';clearMeasurement();controls();}
function upload(file){return new Promise((resolve,reject)=>{const body=new FormData();body.append('file',file);const xhr=new XMLHttpRequest();xhr.open('POST','/catastro/api/planos/importar/');xhr.timeout=120000;xhr.setRequestHeader('X-CSRFToken',$('planos-upload-form').querySelector('[name=csrfmiddlewaretoken]').value);xhr.upload.addEventListener('progress',event=>{if(event.lengthComputable){$('planos-import-progress').value=event.loaded/event.total;const text='Subiendo DWG: '+Math.round(event.loaded/event.total*100)+'% de '+format(file.size/1048576)+' MB.';status(text);importState('uploading',text,file.name);}});xhr.upload.addEventListener('load',()=>importState('uploading','Archivo enviado. Esperando confirmación del servidor…',file.name));xhr.addEventListener('load',()=>{let v;try{v=JSON.parse(xhr.responseText);}catch(_){reject(Error('Inicia sesión para cargar el DWG.'));return;}if(xhr.status===202)resolve(v);else reject(Error(v.error||'No se pudo cargar el DWG.'));});xhr.addEventListener('timeout',()=>reject(Error('El servidor no confirmó la carga en dos minutos. Consulta si el plano quedó recibido antes de intentarlo nuevamente.')));xhr.addEventListener('error',()=>reject(Error('La carga se interrumpió. Vuelve a seleccionar el DWG.')));xhr.send(body);});}
$('planos-file').addEventListener('change',async event=>{
 const file=event.target.files[0];if(!file)return;if(!/\.dwg$/i.test(file.name)){status('Selecciona un archivo DWG.',true);event.target.value='';return;}if(file.size>100*1024*1024){status('Esta instancia admite DWG de hasta 100 MB.',true);event.target.value='';return;}
 reset();importState('uploading','Iniciando subida de '+format(file.size/1048576)+' MB…',file.name);$('planos-import-progress').value=0;
 try {const v=await upload(file);job=v.id;history.replaceState(null,'','?plano='+job);$('planos-import-progress').removeAttribute('value');await poll(job);}
 catch(error){status(error.message,true);importState('failed',error.message);}
});
$('planos-import-retry').addEventListener('click',()=>{if(job)return poll(job);});
$('planos-crs').addEventListener('change',async()=>{serial++;clearMeasurement();measure=null;const names=[...layers.values()].filter(row=>row.visible).map(row=>row.name);layers.forEach(row=>{row.features=[];row.next=0;row.loaded=false;row.loading=false;});draw();if(meta)$('planos-map-caption').textContent=meta.filename+' · '+(geographic()?'sistema seleccionado':'coordenadas CAD sin ubicación confirmada');for(const name of names)await load(name,true);});
function clearMeasurement(){measurement?.setMap(null);measurement=null;points=[];$('planos-measure-result').textContent=geographic()?'Selecciona una herramienta y marca puntos en el mapa.':'Confirma el sistema de coordenadas para medir en metros sobre Google Maps.';}
function mode(value){if(!geographic()||!map)return;clearMeasurement();measure=measure===value?null:value;['distance','area'].forEach(key=>$('planos-'+key).setAttribute('aria-pressed',String(measure===key)));map.setOptions({draggableCursor:measure?'crosshair':null});}
function addMeasurement(point){points.push(point);measurement?.setMap(null);const area=measure==='area';measurement=area?new google.maps.Polygon({map,paths:points,fillColor:'#65b8ff',fillOpacity:.2,strokeColor:'#65b8ff',clickable:false}):new google.maps.Polyline({map,path:points,strokeColor:'#65b8ff',clickable:false});const g=google.maps.geometry.spherical;$('planos-measure-result').textContent=area?(points.length<3?'Marca al menos tres puntos.':'Área aproximada: '+format(g.computeArea(points))+' m²'):'Distancia aproximada: '+format(g.computeLength(points))+' m';}
$('planos-distance').addEventListener('click',()=>mode('distance'));$('planos-area').addEventListener('click',()=>mode('area'));$('planos-measure-clear').addEventListener('click',clearMeasurement);
$('planos-fit').addEventListener('click',fit);$('planos-remove').addEventListener('click',()=>{reset();history.replaceState(null,'',location.pathname);status('Plano cerrado. Su original permanece guardado.');});
$('planos-panels-toggle').addEventListener('click',()=>{const hidden=!$('planos-panels').hidden;$('planos-panels').hidden=hidden;$('planos-workspace').classList.toggle('planos-panels-hidden',hidden);$('planos-panels-toggle').textContent=hidden?'Mostrar tarjetas':'Ocultar tarjetas';$('planos-panels-toggle').setAttribute('aria-expanded',String(!hidden));});
$('planos-basemap').addEventListener('change',event=>map?.setMapTypeId(event.target.value));$('planos-opacity').addEventListener('input',event=>{$('planos-opacity-value').textContent=event.target.value+'%';draw();});$('planos-layer-search').addEventListener('input',renderLayers);
$('planos-all').addEventListener('click',async()=>{const stamp=serial;for(const row of layers.values()){if(stamp!==serial)break;if(row.drawable){row.visible=true;if(!row.loaded)await load(row.name);}}draw();renderLayers();fit();});
$('planos-none').addEventListener('click',()=>{layers.forEach(row=>row.visible=false);draw();renderLayers();});
$('planos-export').addEventListener('click',()=>{if(!geographic())return;const blob=new Blob([JSON.stringify({type:'FeatureCollection',features:visible()},null,2)],{type:'application/geo+json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='capas-del-plano.geojson';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status('Geometrías cargadas exportadas. El DWG original permanece guardado.');});
const svg=$('planos-cad');
svg.addEventListener('wheel',event=>{event.preventDefault();const f=event.deltaY>0?1.15:1/1.15,[x,y,w,h]=box,W=w*f,H=h*f;if(W>1e-8&&W<1e13)setBox([x+(w-W)/2,y+(h-H)/2,W,H]);},{passive:false});
svg.addEventListener('pointerdown',event=>{if(event.button!==0)return;drag={x:event.clientX,y:event.clientY,box:[...box]};moved=false;});
svg.addEventListener('pointermove',event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>3&&!moved){moved=true;svg.setPointerCapture(event.pointerId);}const scale=Math.max(drag.box[2]/svg.clientWidth,drag.box[3]/svg.clientHeight);setBox([drag.box[0]-dx*scale,drag.box[1]-dy*scale,drag.box[2],drag.box[3]]);});
['pointerup','pointercancel'].forEach(type=>svg.addEventListener(type,event=>{drag=null;if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);}));
window.initPlanosMap=()=>{map=new google.maps.Map($('planos-map'),{center:{lat:-16.3989,lng:-71.535},zoom:15,mapTypeControl:false,streetViewControl:false,fullscreenControl:false,gestureHandling:'greedy'});map.addListener('click',event=>{if(measure&&geographic())addMeasurement(event.latLng);});map.addListener('mousemove',event=>{$('planos-coordinates').textContent=event.latLng.lat().toFixed(6)+', '+event.latLng.lng().toFixed(6)+' · WGS84';});controls();if(meta&&geographic()){draw();fit();}if(!job)status('Abre un archivo DWG para explorar sus capas.');};
window.gm_authFailure=()=>{if(!job||geographic())status('Google Maps no pudo autorizar este dominio. La vista CAD sigue disponible.',true);};
controls();const previous=new URLSearchParams(location.search).get('plano');if(previous&&/^[a-f0-9]{32}$/.test(previous)){job=previous;poll(job);}else status('Abre un archivo DWG para explorar sus capas.');
})();
