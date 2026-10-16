const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const sandbox={window:{},URLSearchParams,AbortController,setTimeout,clearTimeout};
for(const name of ['geollaqta-data.js','geollaqta-district.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js',name),'utf8'),sandbox);
const info={ubigeo:'040126',service_base:'https://geo.example/MapServer',layers:{lotes:{id:10,name:'Lotes',fields:'OBJECTID,ID_DIST,ID_LOTE',kind:'polygon'}}};
const reply=data=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>data});
const raw=(id,district='040126')=>({attributes:{OBJECTID:id,ID_DIST:district,ID_LOTE:district+'07001001'},geometry:{rings:[[[-71.5,-16.4],[-71.499,-16.4],[-71.499,-16.399],[-71.5,-16.4]]]}});
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
async function main(){
 let active=0,max=0,inventory=0;const calls=[],progress=[];
 const loader=sandbox.window.GeollaqtaDistrict.create(async(url,options)=>{
  const p=options.body;assert.equal(p.has('geometry'),false,'A complete district must not be clipped to the viewport.');
  if(p.get('returnIdsOnly')){inventory++;assert.equal(p.get('where'),"ID_DIST='040126'");return reply({objectIds:Array.from({length:1201},(_,i)=>i+1)});}
  const ids=p.get('objectIds').split(',').map(Number);calls.push(ids);assert.ok(ids.length<=500);active++;max=Math.max(max,active);await flush();active--;
  return reply({features:ids.map(id=>raw(id))});
 });
 const result=await loader.load(info,'lotes',{onBatch:(batch,data)=>progress.push({size:data.features.length,complete:data.complete})});
 assert.equal(result.features.length,1201);assert.equal(result.processed,1201);assert.equal(result.complete,true);assert.equal(result.truncated,false);assert.equal(calls.length,3);assert.equal(max,2);
 assert.ok(progress.some(p=>p.size>0&&p.size<1201&&!p.complete),'Draw partial batches before the full district finishes.');
 await loader.load(info,'lotes');assert.equal(inventory,1);assert.equal(calls.length,3,'Rechecking a complete district reuses geometry.');
 let failed=true;const seen=[],resumable=sandbox.window.GeollaqtaDistrict.create(async(url,options)=>{
  const p=options.body;if(p.get('returnIdsOnly'))return reply({objectIds:Array.from({length:1201},(_,i)=>i+1)});
  const ids=p.get('objectIds').split(',').map(Number);seen.push(ids[0]);if(failed&&ids[0]===501){failed=false;throw Error('network unavailable');}
  return reply({features:ids.map(id=>raw(id))});
 });
 await assert.rejects(resumable.load(info,'lotes'),/network/);const completed=seen.filter(id=>id!==501);
 const before=seen.length;const resumed=await resumable.load(info,'lotes',{force:true});
 assert.equal(resumed.features.length,1201);assert.ok(seen.slice(before).every(id=>!completed.includes(id)),'Retry resumes missing blocks without downloading completed blocks.');
 let mismatch=true;const strict=sandbox.window.GeollaqtaDistrict.create(async(url,options)=>options.body.get('returnIdsOnly')?reply({objectIds:[1,2]}):reply({features:mismatch?[raw(1)]:[raw(1),raw(2)]}));
 await assert.rejects(strict.load(info,'lotes'),/incompleto/);mismatch=false;assert.equal((await strict.load(info,'lotes')).features.length,2);
 const foreign=sandbox.window.GeollaqtaDistrict.create(async(url,options)=>options.body.get('returnIdsOnly')?reply({objectIds:[1]}):reply({features:[raw(1,'150101')]}));
 await assert.rejects(foreign.load(info,'lotes'),/otro distrito/);
 const empty=sandbox.window.GeollaqtaDistrict.create(async()=>reply({objectIds:null}));assert.equal((await empty.load(info,'lotes')).complete,true);
 let release;const stop=new AbortController(),stale=[];
 const cancellable=sandbox.window.GeollaqtaDistrict.create(async(url,options)=>options.body.get('returnIdsOnly')?reply({objectIds:[1]}):new Promise(resolve=>release=()=>resolve(reply({features:[raw(1)]}))));
 const old=cancellable.load(info,'lotes',{signal:stop.signal,onBatch:(batch,data)=>stale.push(data.processed)});await flush();stop.abort();release();await assert.rejects(old,{name:'AbortError'});assert.ok(stale.every(n=>n===0),'Late aborted blocks must not enter cache or render.');
 console.log('Complete district: 1201 polygons, progressive batches, max 2 requests, no viewport/cap, cache, resume, missing IDs, foreign district and stale cancellation passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
