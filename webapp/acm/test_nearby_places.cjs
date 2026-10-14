const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'static/acm/js/nearby-places.js'),'utf8');
const flush=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
function fixture(options={}) {
  const elements=new Map(),events={},timers=new Map(),calls=[],pins=[];let timerId=0;
  class Element {
    constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.hidden=false;this.value='';this.events={};this.textContent='';this.offsetWidth=350;}
    append(...children){this.children.push(...children);} replaceChildren(...children){this.children=children;this.textContent='';}
    addEventListener(name,callback){this.events[name]=callback;} setAttribute(name,value){this[name]=value;} scrollIntoView(){}
  }
  const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  el('cmp-nearby').hidden=true;el('cmp-form').dataset.authenticated=options.anonymous?'false':'true';
  el('cmp-nearby-radius').value='5000';el('cmp-nearby-sort').value='WALKING';
  const place=(category,index)=>({id:category+'-'+index,displayName:category+' '+index,formattedAddress:'Dirección de prueba',location:{lat:-16.40+index*.001,lng:-71.53}});
  const maps={importLibrary:async name=>name==='places'?{Place:{searchNearby:request=>{
    calls.push({kind:'places',request});if(options.denyPlaces)return Promise.reject({code:'PERMISSION_DENIED'});
    if(options.deferPlaces)return options.deferPlaces(request);
    return Promise.resolve({places:[place(request.includedPrimaryTypes[0],0),place(request.includedPrimaryTypes[0],1)]});
  }},SearchNearbyRankPreference:{DISTANCE:'DISTANCE'}}:{RouteMatrix:{computeRouteMatrix:async request=>{
    calls.push({kind:'matrix',request});if(options.denyRoutes)throw {code:'PERMISSION_DENIED'};
    return {matrix:{rows:[{items:request.destinations.map(p=>{
      const first=p.id.endsWith('-0'),type=p.id.split('-')[0];
      const walking={police:first?600:250,hospital:first?1800:1200,shopping_mall:first?900:650,school:first?350:100}[type];
      return {condition:'ROUTE_EXISTS',distanceMeters:request.travelMode==='WALKING'?walking:first?1500:2200,durationMillis:walking*1000};
    })}]}};
  }},Route:{computeRoutes:async request=>{calls.push({kind:'route',request});return {routes:[{path:[request.origin,{lat:-16.4,lng:-71.53}],distanceMeters:250,durationMillis:180000,warnings:['Cruce peatonal de prueba']}]};}}},
    SymbolPath:{CIRCLE:1},Marker:class{constructor(settings){this.settings=settings;this.events={};pins.push(this);}setMap(map){this.map=map;}addListener(name,callback){this.events[name]=callback;}},
    Polyline:class{constructor(settings){this.settings=settings;}setMap(map){this.map=map;}},LatLngBounds:class{extend(){}}};
  const map={getDiv:()=>({clientWidth:1000}),fitBounds(){}};
  const sandbox={window:{},google:{maps},document:{getElementById:id=>id==='cmp-replication-data'?null:el(id),createElement:tag=>new Element(tag),
    addEventListener:(name,callback)=>events[name]=callback,dispatchEvent(){}},CustomEvent:class{constructor(name){this.type=name;}},Date,
    setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(source,sandbox);const api=sandbox.window.ACMNearby;api.init(map);
  const update=(lat=-16.4,lng=-71.53)=>events['acm:target-location']({detail:{lat,lng}});
  const calculate=(lat=-16.4,lng=-71.53)=>events['acm:search-completed']({detail:{lat,lng}});
  const run=async()=>{const entry=[...timers.entries()].find(([,t])=>t.delay===700);if(entry){timers.delete(entry[0]);await entry[1].callback();}await flush();};
  return {api,el,calls,pins,update,calculate,run,events};
}
async function main(){
  const f=fixture();
  assert.equal(f.api.proximity(300),'blue');assert.equal(f.api.proximity(300.1),'yellow');assert.equal(f.api.proximity(1000),'yellow');assert.equal(f.api.proximity(1000.1),'red');assert.equal(f.api.proximity(null),'unknown');
  assert.equal(f.api.point({lat:null,lng:0}),null);assert.equal(f.api.point({lat:91,lng:0}),null);
  assert.equal(f.api.metric({condition:'ROUTE_NOT_FOUND',distanceMeters:0,durationMillis:0}),null);
  assert.equal(f.api.metric({condition:'ROUTE_EXISTS',distanceMeters:5,durationMillis:61000}).minutes,2);
  assert.equal(f.api.metric({condition:'ROUTE_EXISTS',distanceMeters:0,durationMillis:0}).minutes,0);
  assert.equal(f.el('cmp-nearby').hidden,true);assert.equal(f.calls.length,0,'No queries for the default map center');
  for(let i=0;i<20;i++)f.update(-16.4+i*.00001,-71.53);
  await f.run();assert.equal(f.calls.length,0,'Moving the pin 20 times makes no Places or Routes request');
  assert.equal(f.el('cmp-nearby').hidden,true);
  await f.calculate();assert.equal(f.el('cmp-nearby').hidden,false);
  assert.equal(f.el('cmp-nearby-content').hidden,true,'Search results appear collapsed');
  const initialCalls=f.calls.length;f.el('cmp-nearby-toggle').events.click();
  assert.equal(f.el('cmp-nearby-content').hidden,false);assert.equal(f.calls.length,initialCalls,'Expanding is free of API calls');
  assert.equal(f.calls.filter(c=>c.kind==='places').length,4);assert.equal(f.calls.filter(c=>c.kind==='matrix').length,2);
  const cards=f.el('cmp-nearby-list').children;
  assert.equal(cards.length,4);assert.deepEqual(cards.map(c=>c.dataset.level),['blue','red','yellow','blue']);
  assert.match(cards[0].children[1].textContent,/police 1/,'Nearest walking route can differ from nearest straight-line candidate');
  const drive=f.calls.find(c=>c.kind==='matrix'&&c.request.travelMode==='DRIVING');assert.equal(drive.request.routingPreference,'TRAFFIC_AWARE');
  assert.equal(f.calls.find(c=>c.kind==='matrix'&&c.request.travelMode==='WALKING').request.routingPreference,undefined);
  const routeButton=cards[0].children.find(child=>child.tag==='div').children.find(child=>child.tag==='button');await routeButton.events.click();await flush();
  assert.equal(f.calls.filter(c=>c.kind==='route').length,1);assert.match(f.el('cmp-nearby-route').textContent,/3 min/);
  f.el('cmp-nearby-sort').value='DRIVING';f.el('cmp-nearby-sort').events.change();
  assert.match(f.el('cmp-nearby-list').children[0].children[1].textContent,/police 0/);assert.equal(f.el('cmp-nearby-list').children[0].dataset.level,'red');
  const requests=f.calls.length;f.update();await f.run();assert.equal(f.calls.length,requests,'Selecting the same pin reuses the results');
  f.el('cmp-nearby-radius').value='10000';f.el('cmp-nearby-radius').events.change();await flush();assert.equal(f.calls.length,requests,'Changing radius waits for Buscar y calcular');
  await f.calculate();assert.equal(f.calls.filter(c=>c.kind==='places').length,8,'Only another completed search queries the changed radius');
  f.el('cmp-nearby-close').events.click();assert.equal(f.el('cmp-nearby').hidden,true);assert.equal(f.el('cmp-nearby-route').hidden,true);
  const denied=fixture({denyRoutes:true});await denied.calculate();
  assert.equal(denied.el('cmp-nearby-list').children[0].dataset.level,'unknown');assert.match(denied.el('cmp-nearby-status').textContent,/no autorizó/);
  const anonymous=fixture({anonymous:true});await anonymous.calculate();assert.equal(anonymous.calls.length,0);assert.match(anonymous.el('cmp-nearby-status').textContent,/Inicia sesión/);
  const pending=[];const stale=fixture({deferPlaces:request=>new Promise(resolve=>pending.push({request,resolve}))});const loading=stale.calculate();await flush();
  stale.update(-16.41,-71.54);pending.forEach(p=>p.resolve({places:[]}));await loading;
  assert.equal(stale.el('cmp-nearby-list').children.length,0,'Old origin results cannot overwrite a moved pin');
  assert.equal(stale.calls.filter(c=>c.kind==='matrix').length,0);
  console.log('Nearby places: 20 pin moves without queries, explicit search, collapsed results, radius, routes, cache, login and stale-pin checks passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
