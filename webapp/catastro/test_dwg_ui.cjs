const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/js/visor-planos.js'),'utf8');
class Node{
 constructor(tag='div'){this.tag=tag;this.handlers={};this.children=[];this.dataset={};this.value='';this.attributes={};this.style={};this.clientWidth=1000;this.clientHeight=700;this.classList={toggle(){}};}
 addEventListener(type,fn){this.handlers[type]=fn;}append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;}
 setAttribute(key,value){this.attributes[key]=value;}removeAttribute(key){delete this.attributes[key];}toggleAttribute(key,force){if(force)this.setAttribute(key,'');else this.removeAttribute(key);}querySelector(){return {value:'test-csrf'};}
}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};
get('planos-cad').setAttribute('hidden','');get('planos-crs').value='unknown';get('planos-opacity').value='65';
let uploaded=null,mode='completed',uploadCount=0;const requests=[],timeouts=new Map();let timerId=0;
const feature={type:'Feature',id:1,geometry:{type:'Polygon',coordinates:[[[230000,8185000],[230020,8185000],[230020,8185030],[230000,8185000]]]},properties:{capa:'LOTES',handle:'A1',entidad_cad:'LWPOLYLINE'}};
const meta={id:'a'.repeat(32),filename:'cayma.dwg',bytes:14700000,status:'completed',entities:30050,units:6,bounds:[230000,8185000,230020,8185030],unsupported:{},layers:[{name:'0',count:39,drawable:27,color:'#ffffff',types:{LWPOLYLINE:13,HATCH:11}},{name:'COD_LOTE',count:30112,drawable:30112,color:'#00ffff',types:{TEXT:30100,LWPOLYLINE:9}},{name:'LOTES',count:28300,drawable:28300,color:'#808080',types:{LWPOLYLINE:28300}}]};
class XHR{
 constructor(){this.handlers={};this.uploadHandlers={};this.upload={addEventListener:(t,fn)=>this.uploadHandlers[t]=fn};}open(method,url){assert.equal(method,'POST');assert.equal(url,'/catastro/api/planos/importar/');}setRequestHeader(){}addEventListener(t,fn){this.handlers[t]=fn;}send(body){uploaded=body.file;uploadCount++;assert.equal(get('planos-import-state').dataset.state,'uploading');assert.equal(get('planos-import-file').textContent,body.file.name);if(mode==='timeout'){assert.equal(this.timeout,120000);this.handlers.timeout();return;}this.uploadHandlers.progress({lengthComputable:true,loaded:50,total:100});assert.match(get('planos-import-detail').textContent,/50%/);this.status=202;this.responseText=JSON.stringify({id:meta.id});this.handlers.load();}
}
const context={window:{},document:{getElementById:get,createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag)},
 location:{search:'',pathname:'/catastro/visor-planos/'},history:{replaceState(){}},URLSearchParams,
 XMLHttpRequest:XHR,FormData:class{append(name,file){this[name]=file;}},AbortController,setInterval:()=>1,clearInterval(){},setTimeout(fn,ms){const id=++timerId;timeouts.set(id,{fn,ms});return id;},clearTimeout(id){timeouts.delete(id);},
 fetch:async url=>{requests.push(url);if(mode==='disconnected')throw Error('No se pudo contactar con el servidor.');return {ok:true,headers:{get:()=> 'application/json'},json:async()=>url.includes('/capa/')?{type:'FeatureCollection',features:[feature],next_offset:null}:{...meta,status:mode,message:mode==='failed'?'La conversión falló. El original se conserva.':'Leyendo entidades CAD.'}};}};
(async()=>{
 vm.runInNewContext(source,context);
 const file={name:'cayma.dwg',size:14700000};
 await get('planos-file').handlers.change({target:{files:[file]}});
 assert.equal(uploaded,file,'The actual DWG must be uploaded without reading it as text or JSON.');
 assert.equal(Object.hasOwn(get('planos-cad').attributes,'hidden'),false,'Unknown coordinates must open the CAD view.');
 assert.equal(get('planos-map').hidden,true,'Unknown coordinates must not be guessed on Google Maps.');
 assert.equal(get('planos-cad-entities').children.length,1);
 assert.equal(get('planos-import-state').dataset.state,'completed');
 assert.equal(get('planos-import-progress').hidden,true);
 assert.equal(get('planos-cad-notice').hidden,false,'Explain the dark CAD view beside the coordinate selector.');
 assert.match(requests.find(url=>url.includes('/capa/')),/layer=LOTES&/,'Prefer the cadastral geometry over layer 0 and labels.');
 const path=get('planos-cad-entities').children[0];assert.equal(path.tag,'path');assert.match(path.attributes.d,/230000/);
 path.handlers.click({stopPropagation(){}});
 assert.equal(get('planos-selection').open,true);
 assert.equal(get('planos-selected-layer').textContent,'LOTES');
 const count=requests.length;
 const check=get('planos-layers').children[2].children[0];check.checked=false;await check.handlers.change();
 assert.equal(get('planos-cad-entities').children.length,0,'Unchecking a layer must remove its geometry.');
 assert.equal(requests.length,count,'Hiding a layer must not reimport the DWG.');
 mode='running';await get('planos-file').handlers.change({target:{files:[file]}});
 assert.equal(get('planos-import-state').dataset.state,'reading');assert.match(get('planos-import-detail').textContent,/Leyendo entidades/);assert.equal(get('planos-import-progress').hidden,false);
 mode='failed';await [...timeouts.values()].find(timer=>timer.ms===2000).fn();
 assert.equal(get('planos-import-state').dataset.state,'failed');assert.equal(get('planos-import-progress').hidden,true);assert.equal(get('planos-file').disabled,false);
 mode='disconnected';await get('planos-file').handlers.change({target:{files:[file]}});
 assert.equal(get('planos-import-state').dataset.state,'disconnected');assert.equal(get('planos-import-retry').hidden,false);
 const beforeRetry=uploadCount;mode='completed';await get('planos-import-retry').handlers.click();
 assert.equal(uploadCount,beforeRetry,'Consult the saved job without re-uploading.');assert.equal(get('planos-import-state').dataset.state,'completed');
 mode='timeout';await get('planos-file').handlers.change({target:{files:[file]}});
 assert.equal(get('planos-import-state').dataset.state,'failed');assert.match(get('planos-import-detail').textContent,/dos minutos/);assert.equal(get('planos-import-progress').hidden,true);
 console.log('DWG UI: native upload, progress/errors/retry, cadastral layer priority and CAD explanation verified.');
})().catch(error=>{console.error(error);process.exitCode=1;});
