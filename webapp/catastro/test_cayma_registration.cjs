const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const nodes=new Map(),arrows=[],requests=[],markers=[];
let placement={revision:0,east_m:0,north_m:0,blocks:{},locked:true},permissionFailures=1;
class Element{
 constructor(){this.events={};this.checked=true;this.hidden=false;this.disabled=false;this.dataset={};this.style={};this.textContent='';this.value='5';this.clientHeight=800;}
 addEventListener(k,fn){this.events[k]=fn;}append(){}remove(){}querySelector(){return {value:'csrf-token'};}querySelectorAll(){return arrows;}
 getBoundingClientRect(){return {left:0,top:0};}setPointerCapture(id){this.captured=id;}releasePointerCapture(){this.captured=null;}
}
const el=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
el('cayma-ref-mode').value='block';
for(const move of ['1,0','0,-1']){const e=new Element();e.dataset.caymaMove=move;arrows.push(e);}
function feature(id,west,parent){return {id,properties:{BLOCK_REF:parent},geometry:{type:'Polygon',coordinates:[[[west,-16.36],[west+.001,-16.36],[west+.001,-16.359],[west,-16.359],[west,-16.36]]]}};}
const response=(v,status=200)=>({ok:status===200,status,headers:{get:()=> 'application/json'},json:async()=>v});
const fetcher=async(url,options={})=>{
 requests.push({url,options});
 if(options.method==='POST'){const p=JSON.parse(options.body);assert.equal(options.headers['X-CSRFToken'],'csrf-token');assert.equal(p.locked,true);placement={...p,revision:placement.revision+1};return response(placement);}
 if(url.includes('posicion')){if(permissionFailures-->0)return response({error:'Consulta temporalmente no disponible.'},503);return response(placement);}
 assert.match(url,/original=1/,'The editor always starts with immutable geometry, preventing compound scaling after reload.');
 const isBlock=url.includes('manzanas');return response({placement:structuredClone(placement),bbox:[-71.55,-16.36,-71.53,-16.35],original_bbox:[-71.55,-16.36,-71.53,-16.35],features:[feature(isBlock?'a':'lot-a',-71.55,isBlock?null:'a'),feature(isBlock?'b':'lot-b',-71.54,isBlock?null:'b')]});
};
class Overlay{setMap(){this.onAdd();}getPanes(){return {overlayLayer:new Element()};}getProjection(){return {fromContainerPixelToLatLng:p=>({lng:()=>-71.55+p.x/100000,lat:()=>-16.36+p.y/100000})};}}
class Marker{constructor(options){this.options=options;this.events={};markers.push(this);}addListener(k,v){this.events[k]=v;}setMap(value){this.map=value;}setDraggable(value){this.options.draggable=value;}getPosition(){return {lat:()=>-16.36,lng:()=>-71.55};}}
const context={window:{devicePixelRatio:1},document:{getElementById:el,createElement:()=>new Element()},google:{maps:{OverlayView:Overlay,Marker,Point:class{constructor(x,y){this.x=x;this.y=y;}},SymbolPath:{CIRCLE:'circle'}}},fetch:fetcher,URLSearchParams,location:{search:'?catastro=cayma'},localStorage:{setItem(k){assert.equal(k,'catastro-source-placement');}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/cayma-reference.js'),'utf8'),context);
const flush=async()=>{for(let i=0;i<60;i++)await Promise.resolve();};
const mapDiv=new Element(),map={getDiv:()=>mapDiv,getBounds:()=>null,getCenter:()=>({lat:()=>-16.36,lng:()=>-71.55}),fitBounds(){},options:{draggable:true,scrollwheel:true,disableDoubleClickZoom:false},get(k){return this.options[k];},setOptions(v){Object.assign(this.options,v);}};
function event(kind,x=50,y=50,deltaY=0){const e={pointerId:1,button:0,clientX:x,clientY:y,deltaY,deltaMode:0,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}};mapDiv.events[kind](e);return e;}
(async()=>{
 context.window.CaymaReferenceMap.init(map);await flush();
 assert.equal(requests.length,0,'Backup is hidden and makes no requests until selected.');
 el('cayma-ref-visible').checked=true;el('cayma-ref-visible').events.change();await flush();
 assert.equal(el('cayma-ref-edit').disabled,false);assert.equal(markers.length,0);
 assert.equal(el('cayma-ref-edit').textContent,'Reintentar ajuste');
 await el('cayma-ref-edit').events.click();assert.equal(map.options.draggable,false);
 assert.equal(event('wheel',50,50,-100).prevented,undefined,'No block selected: do not intercept the wheel.');
 assert.equal(event('pointerdown').prevented,true);assert.equal(mapDiv.captured,1);
 event('pointermove',60,50);
 const wheel=event('wheel',60,50,-100);assert.equal(wheel.prevented,true);assert.equal(wheel.stopped,true);
 event('pointermove',70,60);event('pointerup',70,60);
 assert.equal(mapDiv.captured,null);assert.match(el('cayma-ref-selection').textContent,/1 lotes/);
 await el('cayma-ref-lock').events.click();await flush();
 assert.equal(placement.east_m,0);assert.equal(placement.north_m,0);assert.deepEqual(Object.keys(placement.blocks),['a']);
 assert.ok(placement.blocks.a.east_m>20&&placement.blocks.a.east_m<23,'Both drag movements applied despite wheel in between.');
 assert.ok(placement.blocks.a.north_m>10);assert.ok(placement.blocks.a.scale>1.16&&placement.blocks.a.scale<1.17);
 assert.equal(map.options.draggable,true);assert.equal(map.options.scrollwheel,true);
 assert.equal(event('wheel',50,50,-100).prevented,undefined,'Frozen geometry leaves map zoom untouched.');
 const frozen=structuredClone(placement),writes=requests.filter(r=>r.options.method==='POST').length;
 await el('cayma-ref-edit').events.click();event('pointerdown',1050,50);event('wheel',1050,50,100);arrows[0].events.click();
 el('cayma-ref-cancel').events.click();assert.deepEqual(placement,frozen);assert.equal(requests.filter(r=>r.options.method==='POST').length,writes);
 // Source translation remains available and must retain individually saved edits.
 await el('cayma-ref-edit').events.click();el('cayma-ref-mode').value='source';el('cayma-ref-mode').events.change();
 assert.equal(markers[0].options.draggable,true);arrows[0].events.click();arrows[1].events.click();
 await el('cayma-ref-lock').events.click();await flush();assert.equal(placement.east_m,5);assert.equal(placement.north_m,-5);assert.deepEqual(placement.blocks,frozen.blocks);assert.equal(markers[0].map,null);
 // Reload, select the transformed block at its new position, and reset only it.
 await el('cayma-ref-edit').events.click();el('cayma-ref-mode').value='block';el('cayma-ref-mode').events.change();
 event('pointerdown',75,55);event('pointerup',75,55);el('cayma-ref-reset-block').events.click();
 await el('cayma-ref-lock').events.click();await flush();assert.deepEqual(placement.blocks,{});assert.equal(placement.east_m,5);
 console.log('Cayma controls: per-block selection, concurrent drag/wheel, independent edits, reload, reset, cancel, source translation, freeze and access retry passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
