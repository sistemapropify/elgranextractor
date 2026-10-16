const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const layerSource=fs.readFileSync(path.join(__dirname,'../static/js/capas-mapa.js'),'utf8');
const components=fs.readFileSync(path.join(__dirname,'static/acm/js/components.js'),'utf8');

function initializedMap(allowed){
  const calls=[];
  const nodes={'cmp-map':{querySelectorAll:()=>[]},'cmp-address':{}};
  const context={window:{CapasMapa:{init:(...args)=>calls.push(args)}},permissions:{pdm_polygons:allowed},
    $:id=>nodes[id],input:()=>({lat:-16.4,lng:-71.5}),restoredViewport:null,
    google:{maps:{Map:class{addListener(){}},places:{Autocomplete:class{addListener(){}}}}},
    MutationObserver:class{observe(){}},hideGoogleGestureHint(){},drawCircles(){},snapshot:null,result:null};
  vm.runInNewContext(components.slice(components.indexOf('  window.initComponentMap='),components.indexOf('  window.gm_authFailure=')),context);
  context.window.initComponentMap();
  return calls;
}

function layerHarness(){
  const nodes=new Map([
    ['capas-vectoriales-data',{textContent:JSON.stringify([{id:1}])}],
    ['capas-raster-data',{textContent:'[]'}],['zonas-mapa-data',{textContent:'[]'}]
  ]),calls=[],rendered=[],listeners={};
  let response={ok:true,status:200,redirected:false,headers:{get:()=> 'application/json'},json:async()=>({vectoriales:[{id:2}],raster:[],zonas:[]})};
  const context={window:{addEventListener:(key,fn)=>listeners[key]=fn,
      CapaVectorial:{init:()=>rendered.push(JSON.parse(nodes.get('capas-vectoriales-data').textContent))},
      CapaRasterOverlay:{init(){}}},
    document:{hidden:false,getElementById:id=>nodes.get(id),addEventListener(){},dispatchEvent(){}},
    fetch:async(url,options)=>{calls.push({url,options});return response;},Event:class{},setInterval(){},clearInterval(){}};
  vm.runInNewContext(layerSource,context);
  return {api:context.window.CapasMapa,calls,rendered,listeners,setResponse:value=>response=value};
}

(async()=>{
  assert.equal(initializedMap(false).length,0,'Disabled role must not start polygon loading or refresh timers.');
  const enabled=initializedMap(true);
  assert.equal(enabled.length,1);
  assert.equal(enabled[0][1].configUrl,'/acm/capas-mapa/');
  const acm=layerHarness();acm.api.init({}, {configUrl:'/acm/capas-mapa/'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(acm.calls[0].url,'/acm/capas-mapa/','ACM must use its own permission-checked session endpoint.');
  assert.equal(acm.rendered.at(-1)[0].id,2);
  acm.setResponse({ok:false,status:403});await acm.api.refresh();
  assert.equal(acm.rendered.at(-1).length,0,'Revoked permission must remove already visible layers.');
  acm.setResponse({ok:false,status:401});await acm.api.refresh();
  assert.equal(acm.rendered.at(-1).length,0,'Expired sessions must not leave layers visible.');
  const quadrants=layerHarness();quadrants.api.init({});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(quadrants.calls[0].url,'/cuadrantizacion/capas-mapa/','Cuadrantizacion retains its existing endpoint.');
  console.log('PDM permissions: disabled role, ACM refresh, revoked permission and Cuadrantizacion verified.');
})().catch(error=>{console.error(error);process.exitCode=1;});
