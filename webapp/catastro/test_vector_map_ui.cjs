const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/js/visor-planos.js'),'utf8');
class Element{
 constructor(tag='div'){this.tag=tag;this.handlers={};this.children=[];this.dataset={};this.value='';this.attributes={};this.style={};this.clientWidth=1000;this.clientHeight=700;this.classList={toggle(){}};}
 addEventListener(name,fn){this.handlers[name]=fn;}append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}toggleAttribute(k,force){if(force)this.setAttribute(k,'');else this.removeAttribute(k);}querySelector(){return{value:'test-csrf'};}
}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
get('planos-crs').value='unknown';get('planos-opacity').value='65';
const rectangle=(id,x)=>({type:'Feature',id,properties:{capa:'LOTES',entidad_cad:'LWPOLYLINE'},geometry:{type:'Polygon',coordinates:[[[x,-16.4],[x+.0001,-16.4],[x+.0001,-16.3999],[x,-16.4]]]}});
const label={type:'Feature',id:100,properties:{capa:'NUMEROS_LOTES',entidad_cad:'TEXT',texto:'12'},geometry:{type:'Point',coordinates:[-71.535,-16.4]}};
const mixedLabel={...label,id:101,properties:{...label.properties,capa:'LOTES'}};
const first=rectangle(1,-71.535),second=rectangle(2,-71.534);
const meta={id:'b'.repeat(32),filename:'cayma.dwg',bytes:6150420,status:'completed',entities:62224,units:4,bounds:[226857,8185850,230605,8197063],unsupported:{},layers:[
 {name:'LOTES',count:28300,drawable:28300,color:'#808080',types:{LWPOLYLINE:28300,TEXT:1}},
 {name:'NUMEROS_LOTES',count:27414,drawable:27414,color:'#ffffff',types:{TEXT:27414}}
]};
class Data{
 static instances=[];
 constructor(){Data.instances.push(this);this.features=[];this.addCalls=0;this.handlers={};}
 setMap(map){this.map=map;}addListener(name,fn){this.handlers[name]=fn;}
 addGeoJson(collection){this.addCalls++;for(const raw of collection.features){assert.notEqual(raw.geometry.type,'Point','CAD text must never create a Google Maps pin');this.features.push({raw,getId:()=>raw.id,getProperty:k=>raw.properties[k]});}}
 setStyle(fn){this.style=fn;for(const f of this.features){const style=fn(f);assert.equal(style.fillOpacity,0,'Parcel interiors must remain transparent');assert.equal(style.icon,undefined,'Vector rendering must not define circle icons');}}
}
let mapInstance,resizeEvents=0,fitCalls=0;
const google={maps:{Data,Map:class{constructor(){mapInstance=this;this.handlers={};this.type='roadmap';}addListener(n,f){this.handlers[n]=f;}setOptions(){}getMapTypeId(){return this.type;}setMapTypeId(v){this.type=v;}fitBounds(b){fitCalls++;this.lastBounds=b;}},LatLngBounds:class{extend(){return this;}},event:{trigger(_,name){if(name==='resize')resizeEvents++;}},geometry:{spherical:{computeArea:()=>1}}}};
const requests=[],frames=[];let pageYields=0;
const labelFrames=[],canvasInstances=[];
const context={window:{PlanosLabels:{create:()=>{const canvas={setMap(map){this.map=map;},setFeatures(features,layers,opacity){this.features=features;this.layers=layers;this.opacity=opacity;labelFrames.push(features.filter(f=>f.properties.texto));}};canvasInstances.push(canvas);return canvas;}}},google,document:{getElementById:get,createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)},location:{search:'',pathname:'/catastro/visor-planos/'},history:{replaceState(){}},URLSearchParams,AbortController,
 setInterval:()=>1,clearInterval(){},setTimeout:(fn,ms)=>{if(ms===0){pageYields++;queueMicrotask(fn);}return 1;},clearTimeout(){},requestAnimationFrame:fn=>frames.push(fn),
 XMLHttpRequest:class{constructor(){this.upload={addEventListener(){}};this.handlers={};}open(){}setRequestHeader(){}addEventListener(n,f){this.handlers[n]=f;}send(){this.status=202;this.responseText=JSON.stringify({id:meta.id});this.handlers.load();}},FormData:class{append(){}},
 fetch:async url=>{requests.push(url);const query=new URLSearchParams(url.split('?')[1]||'');let payload=meta;if(url.includes('/capa/')){const labels=query.get('layer')==='NUMEROS_LOTES';payload={features:labels?[label]:query.get('offset')==='2000'?[second]:[first,mixedLabel],next_offset:labels||query.get('offset')==='2000'?null:2000};}return{ok:true,headers:{get:()=> 'application/json'},json:async()=>payload};}
};
const row=name=>get('planos-layers').children.find(n=>n.children[1].textContent===name);
context.window.PlanosFit=require('../static/js/visor-planos-fit.js');
const check=name=>row(name).children[0];
(async()=>{
 vm.runInNewContext(source,context);context.window.initPlanosMap();
 await get('planos-file').handlers.change({target:{files:[{name:'cayma.dwg',size:6150420}]}});
 check('NUMEROS_LOTES').checked=true;await check('NUMEROS_LOTES').handlers.change();
 assert.ok(get('planos-cad-entities').children.some(n=>n.tag==='text'),'CAD mode retains its labels');
 assert.equal(get('planos-cad-entities').children.find(n=>n.tag==='path').attributes.fill,'none');
 const before=requests.length;get('planos-crs').value='EPSG:32719';await get('planos-crs').handlers.change();
 assert.equal(Data.instances.length,0,'Never instantiate thousands of individual Google Maps objects');const data=canvasInstances[0];
 assert.equal(data.features.length,4,'Every vector and label from every page is supplied to the canvas');
 assert.ok(requests.slice(before).some(u=>u.includes('offset=2000')));
 assert.ok(requests.slice(before).some(u=>u.includes('layer=NUMEROS_LOTES')));
 assert.ok(labelFrames.at(-1).some(f=>f.properties.texto==='12'));
 assert.equal(check('NUMEROS_LOTES').disabled,false);assert.equal(check('NUMEROS_LOTES').checked,true);
 assert.ok(resizeEvents>0);const initialRequests=requests.length;
 get('planos-satellite').handlers.click();assert.equal(mapInstance.type,'hybrid');assert.equal(get('planos-basemap').value,'hybrid');
 const firstFits=fitCalls;
 check('LOTES').checked=false;await check('LOTES').handlers.change();assert.equal(data.features.length,1);
 check('LOTES').checked=true;await check('LOTES').handlers.change();assert.equal(data.features.length,4);
 assert.equal(requests.length,initialRequests,'Do not re-download a loaded layer');
 get('planos-opacity').value='25';get('planos-opacity').handlers.input({target:{value:'25'}});get('planos-opacity').handlers.input({target:{value:'25'}});
 assert.equal(frames.length,1);frames.shift()();assert.equal(data.opacity,.25);assert.equal(canvasInstances.length,1);
 assert.ok(pageYields>0);assert.equal(row('LOTES').children.length,3);
 const beforeAll=requests.length;await get('planos-all').handlers.click();assert.equal(requests.length,beforeAll);
 get('planos-crs').value='unknown';await get('planos-crs').handlers.change();
 assert.equal(data.map,null);assert.equal(check('NUMEROS_LOTES').disabled,false);
 assert.ok(get('planos-cad-entities').children.some(n=>n.tag==='text'),'Switching back restores the visible CAD text layer');
 get('planos-crs').value='EPSG:24879';await get('planos-crs').handlers.change();
 assert.equal(canvasInstances.length,2,'Changing CRS invalidates geographic geometry instead of reusing stale coordinates');
 assert.equal(fitCalls,firstFits+1,'Only returning to the CAD view fits that original view; later CRS changes preserve the map camera');
 assert.equal(mapInstance.type,'hybrid','CRS changes retain the satellite basemap');
 assert.notEqual(canvasInstances[1],data);assert.ok(mapInstance.lastBounds);
 console.log('Vector map: complete vector and text layers, no circle pins/fills, cached geometry, automatic pages, opacity throttling and CRS changes verified.');
})().catch(e=>{console.error(e);process.exitCode=1;});
