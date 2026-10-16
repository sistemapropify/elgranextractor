const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),events={},requests=[],timers=new Map();let timerId=0,hold=true,fail=false;const gates=[];
class Element{
 constructor(){this.events={};this.hidden=false;this.checked=true;this.dataset={};this.children=[];this.attributes={};this.value='';this.textContent='';}
 addEventListener(t,fn){this.events[t]=fn;}setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}replaceChildren(...v){this.children=v;}append(...v){this.children.push(...v);}
}
const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};get('cmp-form').elements={lat:new Element(),lng:new Element()};
const polygon=(x,y,w,h)=>({rings:[[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]]});
const sector=(id,x)=>({attributes:{OBJECTID:x+1,ID_DIST:id},geometry:polygon(x,0,10,10)});
function lot(id,district='040126'){
 const index=id-1,x=id===1?0:id===2?.6:2+(index%50)*.1,y=id<=2?0:2+Math.floor(index/50)*.1;
 return {attributes:{OBJECTID:id,ID_LOTE:district+'07001'+String(id).padStart(3,'0').slice(-3),ID_DIST:district,COD_SECT:'07',COD_MZNA:'001',COD_LOTE:String(id).padStart(3,'0').slice(-3),ANIO_CAT:'2013'},geometry:polygon(district==='040102'?20:x,district==='040102'?0:y,id<=2?.4:.08,id<=2?1:.08)};
}
const config={revision:2,scope:'district',batch_size:500,providers:[{id:'geollaqta',active:true,service_base:'https://geo.example/cadastre',sector_layer:13,lot_layer:10,province_ubigeo:'0401',boundaries:{service_base:'https://geo.example/boundaries',layer:0},districts:[{ubigeo:'040126',name:'Yanahuara'},{ubigeo:'040102',name:'Alto Selva Alegre'}]}]};
class Data{
 constructor(){this.features=[];this.styles=new Map();this.drawSizes=[];Data.instances.push(this);}
 addGeoJson(data){this.features.push(...data.features.map(raw=>({getId:()=>raw.id,raw})));this.drawSizes.push(this.features.length);}
 forEach(fn){[...this.features].forEach(fn);}remove(f){this.features=this.features.filter(x=>x!==f);}setMap(value){this.map=value;}setStyle(value){this.style=value;}
 getFeatureById(id){return this.features.find(f=>f.getId()===id);}overrideStyle(f,style){this.styles.set(f.getId(),style);}revertStyle(f){if(f)this.styles.delete(f.getId());}
 styleFor(f){return {...this.style,...this.styles.get(f.getId())};}
}Data.instances=[];
const response=value=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>value});
async function fetcher(url,options={}){
 requests.push({url,options});if(fail)throw TypeError('offline');
 if(url.includes('/configuracion/'))return response(config);
 if(url.includes('/acm/catastro/lotes/'))return response({lot_id:url.split('/lotes/')[1].split('/')[0],verified:true,metrics:{land_area:'200',built_area:'20.5',floors:null,units:null,boundaries:{frente:'10'}},facade_url:null,reports:[]});
 const p=options.body;assert.equal(p.has('resultRecordCount'),false,'No unsupported ArcGIS pagination.');
 if(url.endsWith('/13/query')){assert.equal(p.get('geometryType'),'esriGeometryPoint');const x=JSON.parse(p.get('geometry')).x;return response({features:x<10?[sector('040126',0)]:x<30?[sector('040102',20)]:[]});}
 if(url.includes('/boundaries/'))return response({features:[]});
 if(p.get('geometryType'))return response({features:[]});
 assert.ok(["ID_DIST='040126'","ID_DIST='040102'"].includes(p.get('where')),'Each download must target exactly one district.');
 assert.doesNotMatch(p.get('where'),/COD_MZNA|COD_SECT/,'The inventory must cover the entire district.');
 const district=p.get('where').includes('040126')?'040126':'040102',ids=district==='040126'?Array.from({length:1201},(_,i)=>i+1):[1];
 if(p.get('returnIdsOnly'))return response({objectIds:ids});
 assert.doesNotMatch(p.get('outFields'),/AREA_TER|AREA_CON|NIVELES/,'Never request GIS measurements for the card.');
 const selected=p.get('objectIds').split(',').map(Number);assert.ok(selected.length<=500);
 if(hold)await new Promise(resolve=>gates.push(resolve));
 return response({features:selected.map(id=>lot(id,district))});
}
const context={window:{ACMPermissions:{cadastral_info:true}},document:{getElementById:id=>id.endsWith('-data')?null:get(id),createElement:()=>new Element(),addEventListener:(name,fn)=>events[name]=fn},google:{maps:{Data}},fetch:fetcher,AbortController,URLSearchParams,setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout(id){timers.delete(id);}};
for(const name of ['static/js/geollaqta-data.js','static/js/catastro-master-data.js','acm/static/acm/js/cadastral-info.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'..',name),'utf8'),context);
const flush=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
async function move(lng,lat=.2){events['acm:target-location']({detail:{lat,lng}});const entry=[...timers].find(([,v])=>v.ms===450);timers.delete(entry[0]);return await entry[1].fn();}
(async()=>{
 const map={};context.window.ACMCadastral.init(map);context.window.ACMCadastral.init(map);assert.equal(Data.instances.length,1);assert.equal(requests.length,0);assert.equal(events.idle,undefined);
 const first=move(.5);await flush();assert.equal(gates.length,2,'Two bounded parallel batches begin.');
 const second=move(.75);await flush();assert.ok(requests.filter(r=>r.options.body?.get('objectIds')).every(r=>!r.options.signal.aborted),'Moving the pin in the same district must not cancel its download.');
 hold=false;gates.splice(0).forEach(resolve=>resolve());await Promise.all([first,second]);await flush();
 const layer=Data.instances[0];assert.equal(layer.features.length,1201,'Load all lots, including more than the old 1000 limit.');assert.equal(layer.map,map);assert.ok(layer.drawSizes.some(n=>n>0&&n<1201),'Lots appear progressively.');
 assert.equal(requests.filter(r=>r.options.body?.get('returnIdsOnly')).length,1,'Same-district movement shares the inventory and active download.');
 assert.equal(get('cmp-cadastral-code').textContent,'04012607001002');assert.equal(get('cmp-cadastral-land').textContent,'200');assert.equal(get('cmp-cadastral-built').textContent,'20.5');
 assert.equal(layer.styleFor(layer.features.find(f=>f.getId()===2)).strokeWeight,2.6);assert.equal(layer.style.clickable,false);
 const before=requests.filter(r=>r.url.startsWith('https://')).length;
 await move(.2);await flush();assert.equal(requests.filter(r=>r.url.startsWith('https://')).length,before,'Repositioning in a loaded district uses its cache.');assert.equal(get('cmp-cadastral-code').textContent,'04012607001001');
 await move(.5);assert.equal(layer.features.length,1201,'A pin on a street must keep the whole district visible.');assert.match(get('cmp-cadastral-status').textContent,/no está dentro de un lote/);
 get('cmp-cadastral-visible').checked=false;get('cmp-cadastral-visible').events.change();assert.equal(layer.map,null);get('cmp-cadastral-visible').checked=true;get('cmp-cadastral-visible').events.change();assert.equal(layer.map,map);
 await move(20.2);assert.equal(layer.features.length,1,'A different district replaces the previous one.');assert.match(get('cmp-cadastral-hint').textContent,/Alto Selva Alegre/);
 await move(60);assert.equal(layer.features.length,0);assert.match(get('cmp-cadastral-status').textContent,/fuera del catálogo/);
 // Resume a district after one failed batch; never restart completed batches.
 const spatial=context.window.CatastroMasterData;let failed=false,inventoryCalls=0;const batchCalls=[],progress=[];
 const provider=spatial.create(config,async(url,options)=>{
  const p=options.body;if(p.get('returnIdsOnly')){inventoryCalls++;return response({objectIds:Array.from({length:1201},(_,i)=>i+1)});}
  const ids=p.get('objectIds').split(',').map(Number);batchCalls.push(ids[0]);if(ids[0]===1001&&!failed){failed=true;throw TypeError('temporary outage');}return response({features:ids.map(n=>lot(n))});
 });
 const district={code:'040126',name:'Yanahuara'};await assert.rejects(provider.loadDistrict(district,{onBatch:(_,v)=>progress.push(v.processed)}));
 assert.ok(progress.includes(1000));const result=await provider.loadDistrict(district);assert.equal(result.lots.features.length,1201);assert.equal(inventoryCalls,1);assert.deepEqual(batchCalls,[1,501,1001,1001]);
 // National boundaries use two-digit component codes; construct the full UBIGEO.
 const boundaryProvider=spatial.create(config,async(url,options)=>response({features:url.includes('/boundaries/')?[{attributes:{ID_DPTO:'04',ID_PROV:'01',ID_DIST:'26'},geometry:polygon(0,0,10,10)}]:[]}));
 assert.equal((await boundaryProvider.districtAt({lng:.5,lat:.2})).code,'040126');
 const g={type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,1],[0,0]],[[.2,.2],[.4,.2],[.4,.4],[.2,.4],[.2,.2]]]};assert.equal(spatial.contains(g,{lng:.3,lat:.3},true),false);assert.equal(spatial.contains(g,{lng:0,lat:.5},true),false);
 const count=Data.instances.length;context.window.ACMPermissions.cadastral_info=false;context.window.ACMCadastral.init({});assert.equal(Data.instances.length,count);
 console.log('ACM district cadastre: basic access, 1201 lots, progressive drawing, streets, moving pin, cache, replacement, resumable batches and boundary UBIGEO passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
