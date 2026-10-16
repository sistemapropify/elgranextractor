const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/js/visor-planos.js'),'utf8');
class Node{
 constructor(tag='div'){this.tag=tag;this.handlers={};this.children=[];this.dataset={};this.value='';this.attributes={};this.style={};this.clientWidth=1000;this.clientHeight=700;this.classList={toggle(){}};}
 addEventListener(type,fn){this.handlers[type]=fn;}append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;}
 setAttribute(key,value){this.attributes[key]=value;}removeAttribute(key){delete this.attributes[key];}querySelector(){return {value:'test-csrf'};}
}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};
get('planos-crs').value='unknown';get('planos-opacity').value='65';
let uploaded=null;const requests=[];
const feature={type:'Feature',id:1,geometry:{type:'Polygon',coordinates:[[[230000,8185000],[230020,8185000],[230020,8185030],[230000,8185000]]]},properties:{capa:'LOTES',handle:'A1',entidad_cad:'LWPOLYLINE'}};
const meta={id:'a'.repeat(32),filename:'cayma.dwg',bytes:14700000,status:'completed',entities:1,units:6,bounds:[230000,8185000,230020,8185030],unsupported:{},layers:[{name:'LOTES',count:1,drawable:1,color:'#00ff00',types:{LWPOLYLINE:1}}]};
class XHR{
 constructor(){this.handlers={};this.upload={addEventListener(){}};}open(method,url){assert.equal(method,'POST');assert.equal(url,'/catastro/api/planos/importar/');}setRequestHeader(){}addEventListener(t,fn){this.handlers[t]=fn;}send(body){uploaded=body.file;this.status=202;this.responseText=JSON.stringify({id:meta.id});this.handlers.load();}
}
const context={window:{},document:{getElementById:get,createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag)},
 location:{search:'',pathname:'/catastro/visor-planos/'},history:{replaceState(){}},URLSearchParams,
 XMLHttpRequest:XHR,FormData:class{append(name,file){this[name]=file;}},setTimeout(){},clearTimeout(){},
 fetch:async url=>{requests.push(url);return {ok:true,headers:{get:()=> 'application/json'},json:async()=>url.includes('/capa/')?{type:'FeatureCollection',features:[feature],next_offset:null}:meta};}};
(async()=>{
 vm.runInNewContext(source,context);
 const file={name:'cayma.dwg',size:14700000};
 await get('planos-file').handlers.change({target:{files:[file]}});
 assert.equal(uploaded,file,'The actual DWG must be uploaded without reading it as text or JSON.');
 assert.equal(get('planos-cad').hidden,false,'Unknown coordinates must open the CAD view.');
 assert.equal(get('planos-map').hidden,true,'Unknown coordinates must not be guessed on Google Maps.');
 assert.equal(get('planos-cad-entities').children.length,1);
 const path=get('planos-cad-entities').children[0];assert.equal(path.tag,'path');assert.match(path.attributes.d,/230000/);
 path.handlers.click({stopPropagation(){}});
 assert.equal(get('planos-selection').open,true);
 assert.equal(get('planos-selected-layer').textContent,'LOTES');
 const count=requests.length;
 const check=get('planos-layers').children[0].children[0];check.checked=false;await check.handlers.change();
 assert.equal(get('planos-cad-entities').children.length,0,'Unchecking a layer must remove its geometry.');
 assert.equal(requests.length,count,'Hiding a layer must not reimport the DWG.');
 console.log('DWG UI: native upload, CAD preview, layer selection and property inspection verified.');
})().catch(error=>{console.error(error);process.exitCode=1;});
