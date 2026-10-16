const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),events={},requests=[],timers=new Map(),labelUpdates=[],gates=[];
let timerId=0,hold=true,documentsFailed=false;
class Element{
 constructor(){this.events={};this.hidden=false;this.dataset={};this.children=[];this.attributes={};this.value='';this.textContent='';}
 addEventListener(t,fn){this.events[t]=fn;}setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}replaceChildren(...v){this.children=v;}append(...v){this.children.push(...v);}
}
const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const origin={lat:-16.4,lng:-71.5},metre=1/111195,at=(east=0,north=0)=>({lat:origin.lat+north*metre,lng:origin.lng+east*metre/Math.cos(origin.lat*Math.PI/180)});
get('cmp-form').elements={lat:new Element(),lng:new Element(),radius:new Element()};get('cmp-form').elements.radius.value='500';
const polygon=(p,w=20,h=20)=>{const dx=w*metre/Math.cos(p.lat*Math.PI/180),dy=h*metre;return {rings:[[[p.lng-dx/2,p.lat-dy/2],[p.lng+dx/2,p.lat-dy/2],[p.lng+dx/2,p.lat+dy/2],[p.lng-dx/2,p.lat+dy/2],[p.lng-dx/2,p.lat-dy/2]]]};};
function lot(id){
 const district=id===2?'040104':'040126',p=id===1?at():id===2?at(100):id===3?at(498):id===2001?at(800):at(-300+(id%40)*10,60+Math.floor((id-4)/40)*10);
 const block=String(Math.floor((id-1)/999)+1).padStart(3,'0'),number=String((id-1)%999+1).padStart(3,'0');
 return {attributes:{OBJECTID:id,ID_LOTE:district+'07'+block+number,ID_DIST:district,COD_SECT:'07',COD_MZNA:block,COD_LOTE:number,ANIO_CAT:'2013'},geometry:polygon(p)};
}
const config={revision:3,scope:'radius',batch_size:500,providers:[{id:'geollaqta',active:true,service_base:'https://geo.example/cadastre',lot_layer:10,districts:[{ubigeo:'040126',name:'Yanahuara'},{ubigeo:'040104',name:'Cerro Colorado'}]}]};
class Data{
 constructor(){this.features=[];this.styles=new Map();this.drawSizes=[];Data.instances.push(this);}
 addGeoJson(data){this.features.push(...data.features.map(raw=>({getId:()=>raw.id,raw})));this.drawSizes.push(this.features.length);}
 forEach(fn){[...this.features].forEach(fn);}remove(f){this.features=this.features.filter(x=>x!==f);}setMap(value){this.map=value;}setStyle(value){this.style=value;}
 getFeatureById(id){return this.features.find(f=>f.getId()===id);}overrideStyle(f,style){this.styles.set(f.getId(),style);}revertStyle(f){if(f)this.styles.delete(f.getId());}
 styleFor(f){return {...this.style,...this.styles.get(f.getId())};}
}Data.instances=[];
const response=value=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>value});
function inventory(p){
 assert.equal(p.get('geometryType'),'esriGeometryPolygon');assert.equal(p.get('spatialRel'),'esriSpatialRelIntersects');assert.equal(p.get('inSR'),'4326');
 const ring=JSON.parse(p.get('geometry')).rings[0];assert.equal(ring.length,97);assert.ok(p.get('where').includes("'040104'"));assert.ok(p.get('where').includes("'040126'"),'The radius includes neighbouring districts.');
 const lng=(Math.min(...ring.map(p=>p[0]))+Math.max(...ring.map(p=>p[0])))/2;
 return lng>at(2000).lng?[]:lng>at(600).lng?[3,2001]:Array.from({length:1201},(_,i)=>i+1);
}
async function fetcher(url,options={}){
 requests.push({url,options});
 if(url.includes('/configuracion/'))return response(config);
 if(url.includes('/acm/catastro/lotes/'))return response({lot_id:url.split('/lotes/')[1].split('/')[0],verified:!documentsFailed,document_status:documentsFailed?'unavailable':'verified',metrics:{land_area:'200',built_area:'20.5',floors:null,units:null,boundaries:{frente:'10'}},facade_url:null,reports:[]});
 assert.ok(url.endsWith('/10/query'),'Do not load a district, sector or boundary inventory.');
 const p=options.body;assert.equal(p.has('resultRecordCount'),false);
 if(p.get('returnIdsOnly'))return response({objectIds:inventory(p)});
 assert.doesNotMatch(p.get('outFields'),/AREA_TER|AREA_CON|NIVELES/);
 const ids=p.get('objectIds').split(',').map(Number);assert.ok(ids.length<=500);
 if(hold)await new Promise(resolve=>gates.push(resolve));
 return response({features:ids.map(id=>lot(id))});
}
const context={window:{ACMPermissions:{cadastral_info:true},GeollaqtaLabels:{create(map,options){assert.equal(options.minZoom,0);assert.equal(options.lotMinZoom,0);return {setData(lots){labelUpdates.push(lots.length);}};}}},document:{getElementById:id=>id.endsWith('-data')?null:get(id),createElement:()=>new Element(),addEventListener:(name,fn)=>events[name]=fn},google:{maps:{Data}},fetch:fetcher,AbortController,URLSearchParams,setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout(id){timers.delete(id);}};
for(const name of ['static/js/geollaqta-data.js','static/js/catastro-master-data.js','acm/static/acm/js/cadastral-info.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'..',name),'utf8'),context);
const flush=async()=>{for(let i=0;i<60;i++)await Promise.resolve();};
async function fire(){const entry=[...timers].find(([,v])=>v.ms===450);if(!entry)return;timers.delete(entry[0]);return entry[1].fn();}
async function move(east=0,north=0){const p=at(east,north);get('cmp-form').elements.lat.value=p.lat;get('cmp-form').elements.lng.value=p.lng;events['acm:target-location']({detail:p});return fire();}
const gis=()=>requests.filter(r=>r.url.startsWith('https://')).length;
(async()=>{
 const map={};context.window.ACMCadastral.init(map);context.window.ACMCadastral.init(map);assert.equal(Data.instances.length,1);assert.equal(requests.length,0);assert.equal(events.idle,undefined);assert.equal(events.zoom_changed,undefined);
 const first=move();await flush();assert.equal(gates.length,2);
 const second=move(100);await flush();assert.ok(requests.filter(r=>r.options.body?.get('objectIds')).every(r=>!r.options.signal.aborted),'Movement inside the footprint never aborts its active download.');
 hold=false;gates.splice(0).forEach(resolve=>resolve());await Promise.all([first,second]);await flush();
 const layer=Data.instances[0];assert.equal(layer.features.length,1201);assert.equal(layer.map,map);assert.ok(layer.drawSizes.some(n=>n>0&&n<1201));assert.equal(get('cmp-cadastral').attributes['aria-busy'],'false');
 assert.equal(requests.filter(r=>r.options.body?.get('returnIdsOnly')).length,1);
 assert.equal(get('cmp-cadastral-code').textContent,'04010407001002');assert.match(get('cmp-cadastral-hint').textContent,/Cerro Colorado/);assert.equal(get('cmp-cadastral-land').textContent,'200');assert.equal(get('cmp-cadastral-built').textContent,'20.5');
 assert.ok(labelUpdates.includes(1201));assert.equal(get('cmp-cadastral-photo').src,'https://catastro.cofopri.gob.pe/img_catastro/040104/07001002.jpg');assert.equal(layer.styleFor(layer.features.find(f=>f.getId()===2)).strokeWeight,2.6);
 const image=get('cmp-cadastral-photo');image.onerror();assert.match(image.src,/07001002_1\.jpg$/);image.onerror();assert.match(image.src,/07001002_2\.jpg$/,'Missing suffix 1 must not hide an available suffix 2 facade.');image.onload();assert.equal(image.hidden,false);assert.equal(get('cmp-cadastral-photo-status').hidden,true);
 const oldLoaded=image.onload;
 const initial=gis();await move();await flush();assert.equal(gis(),initial,'A new lot inside the loaded radius does not query GIS again.');
 oldLoaded();assert.equal(get('cmp-cadastral-photo-status').hidden,false,'A late photo response from another lot must not replace this lot.');
 const details=requests.filter(r=>r.url.includes('/lotes/')).length;await move(1);await flush();assert.equal(requests.filter(r=>r.url.includes('/lotes/')).length,details,'Movement inside the same lot preserves its pending/cached card.');
 await move(50);assert.equal(gis(),initial,'Street gaps inside the footprint do not trigger a new download.');assert.match(get('cmp-cadastral-status').textContent,/no está dentro de un lote/);
 await move(505);assert.equal(gis(),initial,'A loaded boundary lot remains usable even beyond the original circle.');
 get('cmp-cadastral-close').events.click();assert.equal(layer.map,map);await move();assert.equal(get('cmp-cadastral').hidden,false);
 documentsFailed=true;const batchesBefore=requests.filter(r=>r.options.body?.get('objectIds')).length;
 await move(800);await flush();assert.equal(layer.features.length,2);assert.equal(requests.filter(r=>r.options.body?.get('returnIdsOnly')).length,2,'Leaving the footprint creates one new circular inventory.');
 const newBatches=requests.filter(r=>r.options.body?.get('objectIds')).slice(batchesBefore);assert.deepEqual(newBatches.map(r=>r.options.body.get('objectIds')),['2001'],'Do not download geometry of overlapping lot 3 again.');
 assert.equal(get('cmp-cadastral-land').textContent,'Consulta no disponible');documentsFailed=false;get('cmp-cadastral-retry').events.click();await fire();await flush();assert.equal(get('cmp-cadastral-land').textContent,'200');
 const beforeReturn=gis();await move();await flush();assert.equal(gis(),beforeReturn,'Returning to an earlier footprint reuses its cache.');
 get('cmp-form').elements.radius.value='300';get('cmp-form').elements.radius.events.change();await fire();await flush();assert.equal(requests.filter(r=>r.options.body?.get('returnIdsOnly')).length,3,'Changing the selected radius refreshes its footprint.');
 await move(3000);await flush();assert.equal(layer.features.length,0);assert.match(get('cmp-cadastral-status').textContent,/dentro de este radio/);const empty=gis();await move(3050);assert.equal(gis(),empty,'An empty checked footprint is cached too.');
 const spatial=context.window.CatastroMasterData;assert.ok(Math.abs(spatial.distance(at(),at(500))-500)<1);
 const edge=spatial.circle(origin,500).rings[0];assert.ok(spatial.distance(origin,{lng:edge[0][0],lat:edge[0][1]})>=500);
 let failed=false,inventories=0;const calls=[],progress=[];
 const provider=spatial.create(config,async(url,options)=>{
  const p=options.body;if(p.get('returnIdsOnly')){inventories++;inventory(p);return response({objectIds:Array.from({length:1201},(_,i)=>i+1)});}
  const ids=p.get('objectIds').split(',').map(Number);calls.push(ids[0]);if(ids[0]===1001&&!failed){failed=true;throw TypeError('temporary outage');}return response({features:ids.map(id=>lot(id))});
 });
 await assert.rejects(provider.loadRadius(origin,500,{onBatch:(_,v)=>progress.push(v.processed)}));assert.ok(progress.includes(1000));
 const result=await provider.loadRadius(origin,500);assert.equal(result.lots.features.length,1201);assert.equal(inventories,1);assert.deepEqual(calls,[1,501,1001,1001]);
 // A return to a just-cancelled footprint waits for its old task, then resumes.
 let cancelledInventories=0,cancelledBatches=0;
 const cancelProvider=spatial.create(config,async(url,options)=>{
  if(options.body.get('returnIdsOnly')){cancelledInventories++;return response({objectIds:[1]});}
  if(++cancelledBatches===1)await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{const error=Error('cancelled');error.name='AbortError';reject(error);},{once:true}));
  return response({features:[lot(1)]});
 });
 const stop=new AbortController(),interrupted=cancelProvider.loadRadius(origin,500,{signal:stop.signal});
 const rejected=assert.rejects(interrupted);await flush();stop.abort();const resumed=cancelProvider.loadRadius(origin,500);await rejected;
 assert.equal((await resumed).lots.features.length,1);assert.equal(cancelledInventories,1);assert.equal(cancelledBatches,2);
 await assert.rejects(provider.loadRadius(origin,5000));
 const count=Data.instances.length;context.window.ACMPermissions.cadastral_info=false;context.window.ACMCadastral.init({});assert.equal(Data.instances.length,count);
 console.log('ACM radius cadastre: spatial query, neighbouring districts, retained footprint, streets, boundary lots, overlap reuse, radius change, retries and card/labels passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
