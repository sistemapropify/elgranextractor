const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..');
const nodes=new Map(),events={},requests=[],timers=new Map();let timerId=0,fail=false,blockNumber=1;
class Element {
 constructor(){this.events={};this.hidden=false;this.checked=true;this.dataset={};this.children=[];this.attributes={};this.value='';this.textContent='';}
 addEventListener(t,fn){this.events[t]=fn;}setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}
 replaceChildren(...v){this.children=v;}append(...v){this.children.push(...v);}
}
const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
get('cmp-form').elements={lat:new Element(),lng:new Element()};
function polygon(x,y,w,h){return {rings:[[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]]};}
function block(number=1){return {attributes:{OBJECTID:number,ID_DIST:'040126',COD_SECT:'07',COD_MZNA:String(number).padStart(3,'0'),ANIO_CAT:'2013'},geometry:polygon(number===1?0:2,0,1,1)};}
function lot(id,x,w,number=1){return {attributes:{OBJECTID:id,ID_LOTE:'04012607'+String(number).padStart(3,'0')+String(id).padStart(3,'0'),ID_DIST:'040126',COD_SECT:'07',COD_MZNA:String(number).padStart(3,'0'),COD_LOTE:String(id).padStart(3,'0'),ANIO_CAT:'2013'},geometry:polygon(x,0,w,1)};}
const config={revision:1,max_lots:1000,providers:[{id:'geollaqta',active:true,service_base:'https://geo.example/MapServer',block_layer:11,lot_layer:10,districts:[{ubigeo:'040126',name:'Yanahuara'}]}]};
class Data {
 constructor(){this.features=[];Data.instances.push(this);}addGeoJson(data){this.features.push(...data.features.map(f=>({getId:()=>f.id,raw:f})));}
 forEach(fn){[...this.features].forEach(fn);}remove(f){this.features=this.features.filter(x=>x!==f);}setMap(value){this.map=value;}setStyle(fn){this.style=fn;}
}Data.instances=[];
const response=value=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>value});
async function fetcher(url,options={}){
 requests.push({url,options});
 if(fail)throw Error('offline');
 if(url.includes('/configuracion/'))return response(config);
 if(url.includes('/acm/catastro/lotes/'))return response({lot_id:url.split('/lotes/')[1].split('/')[0],verified:true,metrics:{land_area:'200',built_area:'20.5',floors:null,units:null,boundaries:{frente:'10',derecha:'20',izquierda:'20',fondo:'10'}},facade_url:null,reports:[]});
 const p=options.body;
 if(url.endsWith('/11/query')){
  assert.equal(p.get('geometryType'),'esriGeometryPoint');assert.equal(p.has('resultRecordCount'),false,'This MapServer does not support pagination.');
  const target=JSON.parse(p.get('geometry'));blockNumber=target.x<1?1:2;
  return response({features:target.x>4?[]:[block(blockNumber)]});
 }
 assert.match(p.get('where'),/COD_SECT='07' AND COD_MZNA='00[12]'/,'Every lot query must name the exact block.');
 if(p.get('returnIdsOnly')==='true')return response({objectIds:blockNumber===1?[1,2]:[3]});
 assert.ok(p.get('objectIds'));assert.ok(!p.get('outFields').includes('AREA_'),'Do not request GIS areas for the card.');
 return response({features:blockNumber===1?[lot(1,0,.5),lot(2,.5,.5)]:[lot(3,2,1,2)]});
}
const context={window:{ACMPermissions:{cadastral_info:true}},document:{getElementById:id=>['cmp-role-analysis-data','cmp-replication-data'].includes(id)?null:get(id),createElement:()=>new Element(),addEventListener:(t,fn)=>events[t]=fn},google:{maps:{Data}},fetch:fetcher,URLSearchParams,AbortController,
 setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)};
for(const file of ['static/js/geollaqta-data.js','static/js/catastro-master-data.js','acm/static/acm/js/cadastral-info.js'])vm.runInNewContext(fs.readFileSync(path.join(root,file),'utf8'),context);
async function move(lng,lat=.25){events['acm:target-location']({detail:{lat,lng}});const entry=[...timers].find(([id,v])=>v.ms===450);timers.delete(entry[0]);await entry[1].fn();}
(async()=>{
 const map={};context.window.ACMCadastral.init(map);context.window.ACMCadastral.init(map);
 assert.equal(Data.instances.length,1);assert.equal(requests.length,0,'Do not load the district at startup.');
 assert.equal(events.idle,undefined,'Panning and zooming must not refresh cadastral lots.');
 await move(.25);const layer=Data.instances[0];
 assert.equal(layer.features.length,2);assert.equal(layer.map,map);assert.equal(get('cmp-cadastral-code').textContent,'04012607001001');
 assert.equal(get('cmp-cadastral-land').textContent,'200');assert.equal(get('cmp-cadastral-built').textContent,'20.5');
 assert.equal(layer.style(layer.features[0]).strokeWeight,2.6);assert.equal(layer.style(layer.features[1]).strokeWeight,1.3);
 assert.equal(layer.style(layer.features[0]).clickable,false,'Lot polygons must not intercept pin placement.');
 const geometryCalls=()=>requests.filter(r=>r.url.startsWith('https://')).length,before=geometryCalls();
 await move(.75);assert.equal(geometryCalls(),before,'Reuse the same block geometry when the pin moves within it.');
 assert.equal(get('cmp-cadastral-code').textContent,'04012607001002');
 get('cmp-cadastral-visible').checked=false;get('cmp-cadastral-visible').events.change();assert.equal(layer.map,null);
 get('cmp-cadastral-visible').checked=true;get('cmp-cadastral-visible').events.change();assert.equal(layer.map,map);
 await move(2.25);assert.equal(layer.features.length,1,'Replace the previous block instead of accumulating districts.');assert.equal(get('cmp-cadastral-code').textContent,'04012607002003');
 await move(6);assert.equal(layer.features.length,0);assert.match(get('cmp-cadastral-status').textContent,/no está dentro/);
 fail=true;await move(3.5);assert.equal(layer.features.length,0);assert.equal(get('cmp-cadastral-status').dataset.error,'true');
 const spatial=context.window.CatastroMasterData;
 const g={type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,1],[0,0]],[[.2,.2],[.4,.2],[.4,.4],[.2,.4],[.2,.2]]]};
 assert.equal(spatial.contains(g,{lng:.3,lat:.3},true),false,'A hole is not a cadastral lot.');
 assert.equal(spatial.contains(g,{lng:0,lat:.5},true),false,'Do not assign a shared boundary to an arbitrary lot.');
 const count=Data.instances.length;context.window.ACMPermissions.cadastral_info=false;context.window.ACMCadastral.init({});assert.equal(Data.instances.length,count);
 console.log('ACM cadastral: point/block-only transport, all block lots, pin highlighting, same-block cache, replacement, privacy and errors passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
