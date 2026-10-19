const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),geo=require('../static/js/visor-planos-edit-geometry.js');
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{handlers:{},dataset:{},addEventListener(n,f){this.handlers[n]=f;},setAttribute(){}});return nodes.get(id);};
const block={id:1,properties:{capa:'MANZANAS'},geometry:{type:'Polygon',coordinates:[[[-71,-16],[-70.999,-16],[-70.999,-15.999],[-71,-15.999],[-71,-16]]]}};
const lot={id:2,properties:{capa:'LOTES'},geometry:{type:'Polygon',coordinates:[[[-71,-16],[-70.9995,-16],[-70.9995,-15.999],[-71,-15.999],[-71,-16]]]}};
const label={id:3,properties:{capa:'NUMEROS_LOTES',texto:'1'},geometry:{type:'Point',coordinates:[-70.99975,-15.9995]}};
const features=[block,lot,label],original=JSON.stringify(features),polygons=[],markers=[];
const ll=p=>({lng:()=>p.lng,lat:()=>p.lat});
class Polygon{constructor(o){this.path=o.paths.map(ll);this.handlers={};polygons.push(this);}setMap(){}addListener(n,f){this.handlers[n]=f;}getPath(){return{getAt:i=>this.path[i],setAt:(i,p)=>this.path[i]=p};}}
class Marker{constructor(o){this.point=ll(o.position);this.handlers={};markers.push(this);}setMap(){}addListener(n,f){this.handlers[n]=f;}getPosition(){return this.point;}}
let state={revision:0,groups:[]},fail=false,requests=[],draws=0,prepared=0;
const root={PlanosEditGeometry:geo,google:{maps:{Polygon,Marker,SymbolPath:{CIRCLE:0}}},addEventListener(){},confirm:()=>false};
const context={window:root,document:{getElementById:$,querySelector:()=>({value:'csrf-token'})},URLSearchParams,fetch:async(url,options)=>{requests.push({url,options});if(options.method==='POST'&&!fail){const body=JSON.parse(options.body);assert.equal(body.revision,state.revision);state={revision:state.revision+1,groups:body.groups};}return{ok:!fail,headers:{get:()=> 'application/json'},json:async()=>fail?{error:'Otra sesión guardó cambios.'}:state};}};
vm.runInNewContext(fs.readFileSync(require.resolve('../static/js/visor-planos-editor.js'),'utf8'),context);
const editor=root.PlanosBlockEditor.create({getMap:()=>({setOptions(){}}),getFeatures:()=>features,draw:()=>draws++,stopMeasure(){},prepare:async()=>prepared++});
(async()=>{
 await editor.open('a'.repeat(32),'EPSG:32719');await $('planos-edit-select').handlers.click();assert.equal(prepared,1);
 assert.equal(editor.click(ll({lng:-70.9997,lat:-15.9997})),true);assert.equal($('planos-edit-move').disabled,false);
 $('planos-edit-move').handlers.click();let shape=polygons.at(-1);shape.handlers.dragstart();shape.path=shape.path.map(p=>ll({lng:p.lng()+.0001,lat:p.lat()+.0002}));shape.handlers.dragend();
 let moved=editor.render(features);assert.ok(Math.abs(moved[2].geometry.coordinates[0]-label.geometry.coordinates[0]-.0001)<1e-10);assert.equal(editor.dirty(),true);
 $('planos-edit-vertices').handlers.click();const handle=markers.at(-1);handle.point=ll({lng:-70.99985,lat:-15.9987});handle.handlers.dragend();assert.equal(editor.dirty(),true);
 $('planos-edit-undo').handlers.click();assert.ok(Math.abs(editor.render(features)[2].geometry.coordinates[0]-moved[2].geometry.coordinates[0])<1e-10);
 fail=true;await $('planos-edit-save').handlers.click();assert.equal(editor.dirty(),true);assert.match($('planos-edit-status').textContent,/Otra sesión/);
 fail=false;await $('planos-edit-save').handlers.click();assert.equal(editor.dirty(),false);assert.equal(requests.at(-1).options.headers['X-CSRFToken'],'csrf-token');
 editor.close();await editor.open('a'.repeat(32),'EPSG:32719');assert.ok(Math.abs(editor.render(features)[2].geometry.coordinates[0]-moved[2].geometry.coordinates[0])<1e-10);
 await $('planos-edit-select').handlers.click();editor.click(ll({lng:-70.9996,lat:-15.9995}));$('planos-edit-restore').handlers.click();assert.equal(editor.render(features)[0],block);await $('planos-edit-save').handlers.click();assert.equal(state.groups.length,0);
 assert.equal(JSON.stringify(features),original);assert.ok(draws>=5);console.log('Editor controls: selection, move, corner, undo, save error retention, CSRF, reload and restore verified.');
})().catch(e=>{console.error(e);process.exitCode=1;});
