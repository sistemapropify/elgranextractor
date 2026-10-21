const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor() { this.value=''; this.listeners={}; this.children=[]; this.classList={toggle(){}}; }
  addEventListener(name, callback) { this.listeners[name]=callback; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren() { this.children=[]; }
  setAttribute() {}
  querySelector() { return {value:'test-csrf'}; }
}
const elements = new Map();
const el = id => { if(!elements.has(id))elements.set(id,new Element());return elements.get(id); };
el('district').value='040117';el('collection-workers').value='10';
let errorResponse=null;
let data={totals:{uploaded:0,reports:0,photos:0,missing:0},storage:{configured:true,bucket:'test'},jobs:[],lots:[],r2_bytes:0};
const calls=[];
const sandbox={document:{getElementById:el,createElement:()=>new Element(),addEventListener(){},hidden:false},
  setTimeout:()=>1,clearTimeout(){},console,URL,
  fetch:async(url,options)=>{calls.push({url,options});return errorResponse||{ok:true,headers:{get:()=> 'application/json'},json:async()=>url.includes('/status/')?data:{job_id:'test-job'}};}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/catastro-dashboard.js'),'utf8'),sandbox);
const settle = () => new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await settle();
  assert.equal(el('collection-workers').disabled,false);
  await el('collection-form').listeners.submit({preventDefault(){}});
  const post=calls.find(call=>call.url.endsWith('/start/'));
  assert.equal(JSON.parse(post.options.body).workers,10);
  assert.equal(post.options.headers['X-CSRFToken'],'test-csrf');
  data.jobs=[{id:'test-job',ubigeo:'040117',workers:10,status:'running',district_name:'Distrito',created:1,processed:3,source_objects:20,remaining_objects:17}];
  await el('refresh-collection').listeners.click();
  assert.equal(el('collection-workers').disabled,true);
  assert.equal(el('stop-collection').hidden,false);
  assert.ok(el('jobs-list').children[0].children.some(n=>n.textContent==='Hasta 10 lotes simultáneos'));
  await el('stop-collection').listeners.click();
  assert.ok(calls.some(call=>call.url.endsWith('/jobs/test-job/stop/')));
  data.jobs[0].status='stopped';
  await el('refresh-collection').listeners.click();
  assert.equal(el('collection-workers').disabled,false);
  assert.equal(el('start-collection').textContent,'Reanudar distrito');
  el('collection-workers').value='4';
  await el('collection-form').listeners.submit({preventDefault(){}});
  assert.equal(JSON.parse(calls.filter(call=>call.url.endsWith('/start/')).at(-1).options.body).workers,4);
  errorResponse={status:500,headers:{get:()=> 'text/html'}};
  await el('refresh-collection').listeners.click();
  assert.match(el('collection-message').textContent,/Error del servidor \(500\)/);
  assert.doesNotMatch(el('collection-message').textContent,/Inicia sesión/);
  errorResponse={status:200,redirected:true,url:'http://127.0.0.1:8000/login/?next=/catastro/',headers:{get:()=> 'text/html'}};
  await el('refresh-collection').listeners.click();
  assert.match(el('collection-message').textContent,/Tu sesión venció/);
  errorResponse=null;
  await el('refresh-collection').listeners.click();
  assert.equal(el('collection-message').textContent,'','A successful refresh clears a recovered connection/server error');
  console.log('Collector dashboard: worker selection, active lock, pause and resume passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
