const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element{constructor(){this.checked=false;this.hidden=false;this.textContent='';this.events={};this.dataset={};}addEventListener(k,v){this.events[k]=v;}replaceChildren(){}append(){}}
class Data{constructor(){this.features=new Map();Data.instances.push(this);}forEach(fn){[...this.features.values()].forEach(fn);}remove(f){this.features.delete(f.getId());}setMap(m){this.map=m;}revertStyle(){}setStyle(){}addListener(){}addGeoJson(data){data.features.forEach(raw=>this.features.set(raw.id,{getId:()=>raw.id}));}}Data.instances=[];
const nodes=new Map(),element=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const lotInput=new Element();lotInput.value='lotes';lotInput.checked=true;const count=new Element();count.dataset.geollaqtaCount='lotes';
const pending=[],saved=new Map(),calls=[];let district='040126',scheduled;
const collection=(ids,complete=true)=>({type:'FeatureCollection',name:'Lotes',features:ids.map(id=>({id,type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[]}})),complete,total_in_view:ids.length,processed:ids.length,skipped:0});
const client={get district(){return district;},setDistrict(value){district=value;},catalog:async()=>({districts:[{ubigeo:'040126',name:'Yanahuara',published_lots:5240},{ubigeo:'040104',name:'Cerro Colorado',published_lots:15636}]}),coverage:async()=>({transport:'browser',ubigeo:district,layers:{lotes:{}}}),
 districtLayer:async(info,key,options)=>{const d=district;calls.push({district:d,force:options.force});if(saved.has(d)&&!options.force){const value=saved.get(d);options.onBatch(value.features,value);return value;}
 return new Promise((resolve,reject)=>pending.push({district:d,signal:options.signal,batch(ids){options.onBatch(collection(ids).features,collection(ids,false));},resolve(ids){const value=collection(ids);saved.set(d,value);options.onBatch([],value);resolve(value);},reject}));}};
const numbers={setVisible(v){this.visible=v;},setData(lots){this.lots=lots;}};let fits=0;const map={};
const adapter={createLayer:()=>new Data(),createLabels:()=>numbers,pointIcon:()=>({}),fitFeatures:()=>fits++,getView:()=>{throw Error('District loading must not depend on map bounds or zoom.');},onIdle:()=>{throw Error('Pan and zoom must not schedule district reloads.');}};
const sandbox={window:{GeollaqtaData:{createClient:()=>client,directQuery:async()=>({count:5240})}},document:{getElementById:element,createElement:()=>new Element(),addEventListener(){},querySelector:()=>count,querySelectorAll:selector=>selector.includes('geollaqta-count')?[count]:lotInput.checked?[lotInput]:[]},location:{search:''},URLSearchParams,AbortController,Date,setTimeout:fn=>{scheduled=fn;return 1;},clearTimeout:()=>{scheduled=null;}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/geollaqta-map.js'),'utf8'),sandbox);
const flush=async()=>{for(let i=0;i<60;i++)await Promise.resolve();};
(async()=>{
 element('geollaqta-numbering').checked=true;const control=sandbox.window.GeollaqtaMap.init(map,{adapter});await flush();
 element('geollaqta-visible').checked=true;element('geollaqta-visible').events.change();await flush();
 const first=pending.shift(),layer=Data.instances[0];first.batch([1]);assert.equal(layer.features.size,1,'Render the first block immediately.');first.resolve([1,2]);await flush();
 assert.equal(layer.features.size,2);assert.equal(numbers.lots.length,2);assert.equal(fits,1,'Fit the complete district when first loaded.');const identity=layer.features.get(1);
 element('geollaqta-numbering').events.change();assert.equal(calls.length,1);
 element('geollaqta-refresh').events.click();await flush();assert.equal(layer.features.get(1),identity,'Refresh retains the visible layer while downloading.');
 pending.shift().reject(Error('source failed'));await flush();assert.equal(layer.features.size,2);assert.match(element('geollaqta-status').textContent,/conserva el avance/);
 element('geollaqta-refresh').events.click();await flush();pending.shift().resolve([1,3]);await flush();assert.equal(layer.features.get(1),identity);assert.equal(layer.features.has(2),false);assert.equal(layer.features.has(3),true);
 element('geollaqta-refresh').events.click();await flush();const stale=pending.shift();
 control.setDistrict('040104',false);await flush();assert.equal(layer.features.size,0);const next=pending.shift();assert.equal(next.district,'040104');next.resolve([9]);await flush();stale.resolve([7]);await flush();assert.equal(layer.features.has(9),true);assert.equal(layer.features.has(7),false,'Old district responses cannot paint into the selected district.');
 control.setDistrict('040126',false);await flush();assert.equal(layer.features.has(9),false);
 element('geollaqta-visible').checked=false;element('geollaqta-visible').events.change();await flush();assert.equal(layer.map,null);assert.equal(layer.features.size,0);assert.equal(numbers.visible,false);
 console.log('District map: no zoom/viewport dependency, progressive rendering, full-district framing, retained refresh, district isolation, numbering and stale-response checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
