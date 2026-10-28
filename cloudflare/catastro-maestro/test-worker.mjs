import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {handle} from './worker.mjs';
const sql=new DatabaseSync(':memory:');sql.exec(readFileSync(new URL('schema.sql',import.meta.url),'utf8'));
const DB={prepare(query){let values=[];return {bind(...args){values=args;return this;},async all(){return {results:sql.prepare(query).all(...values)};},async first(){return sql.prepare(query).get(...values)||null;},_run(){const statement=sql.prepare(query);return {results:statement.columns().length?statement.all(...values):(statement.run(...values),[])};}};},async batch(statements){sql.exec('BEGIN');try{const results=statements.map(s=>s._run());sql.exec('COMMIT');return results;}catch(e){sql.exec('ROLLBACK');throw e;}}};
const token='test-only-'.repeat(8);
const VECTORS={async get(key){const data=new TextEncoder().encode('vector-data');return key==='geollaqta/vectores/040102/lotes.part-0001.json.gz'?{body:data,async arrayBuffer(){return data.buffer;}}:null;}};
const env={DB,MASTER_TOKEN:token,VECTORS};
const request=data=>new Request('https://unit.test/v1/database',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(data)});
assert.equal((await handle(new Request('https://unit.test/v1/database',{method:'POST'}),env)).status,401);
assert.equal((await handle(request({action:'read',queries:[{sql:'DELETE FROM meta',params:[]}]}),env)).status,400);
const changes=[{table:'meta',upserts:[['revision','1']],deletes:[]},{table:'projects',upserts:[['pilot','Piloto','PE','040103',34]],deletes:[]}];
const payload={action:'commit',id:crypto.randomUUID(),revision:0,changes,result:{revision:1}};
assert.equal((await handle(request(payload),env)).status,200);
assert.equal((await (await handle(request(payload),env)).json()).replayed,true);
assert.equal(sql.prepare('SELECT count(*) n FROM projects').get().n,1);
assert.equal((await handle(request({...payload,id:crypto.randomUUID(),revision:0}),env)).status,409);
assert.equal(sql.prepare("SELECT value FROM meta WHERE key='revision'").get().value,'1');
// Failure of a later FK write must roll back the revision as well.
const failed={action:'commit',id:crypto.randomUUID(),revision:1,result:{revision:2},changes:[{table:'meta',upserts:[['revision','2']],deletes:[]},{table:'identities',upserts:[['missing-version','lote','x','missing-entity']],deletes:[]}]};
assert.equal((await handle(request(failed),env)).status,502);
assert.equal(sql.prepare("SELECT value FROM meta WHERE key='revision'").get().value,'1');
// A JSON table's own 'id' must not shadow the outer table's primary key.
const removal={action:'commit',id:crypto.randomUUID(),revision:1,result:{revision:2},changes:[{table:'meta',upserts:[['revision','2']],deletes:[]},{table:'projects',upserts:[],deletes:[['pilot']]}]};
assert.equal((await handle(request(removal),env)).status,200);
assert.equal(sql.prepare('SELECT count(*) n FROM projects').get().n,0);
assert.equal(sql.prepare('SELECT count(*) n FROM master_commit_guard').get().n,0);
const versionRows={action:'commit',id:crypto.randomUUID(),revision:2,result:{revision:3},changes:[
  {table:'meta',upserts:[['revision','3']],deletes:[]},
  {table:'sources',upserts:[['source',null,'Fuente','040103',null,'candidate']],deletes:[]},
  {table:'versions',upserts:[['v1','source','V1',null,null,'{}','original.pdf','a'.repeat(64),'b'.repeat(64),'2026-10-20','admin','{}']],deletes:[]}]};
assert.equal((await handle(request(versionRows),env)).status,200);
assert.equal(sql.prepare('SELECT original_sha256 FROM versions').get().original_sha256,'a'.repeat(64));
const review={action:'commit',id:crypto.randomUUID(),revision:3,result:{revision:4},changes:[
  {table:'meta',upserts:[['revision','4']],deletes:[]},
  {table:'catalog_review_status',upserts:[['external_identifiers','candidate-1','observed',4,'2026-10-22T12:00:00Z','admin','Cotejo','{}','v1']],deletes:[]},
  {table:'catalog_review_events',upserts:[['event-1','external_identifiers','candidate-1','observed','candidate',4,'2026-10-22T12:00:00Z','admin','Cotejo','{}','v1']],deletes:[]},
  {table:'journal',upserts:[[4,'catalog_review','admin','2026-10-22T12:00:00Z','Cotejo','{}','{}']],deletes:[]}]};
assert.equal((await handle(request(review),env)).status,200);
assert.equal(sql.prepare('SELECT status FROM catalog_review_status').get().status,'observed');
assert.equal(sql.prepare('SELECT status FROM catalog_review_events').get().status,'observed');
const planMeta={action:'commit',id:crypto.randomUUID(),revision:4,result:{revision:5},changes:[
  {table:'meta',upserts:[['revision','5']],deletes:[]},
  {table:'plan_workspace',upserts:[['source-version:v1','source-version','v1','040103','Plano principal','2026-10-22T13:00:00Z','admin',5]],deletes:[]},
  {table:'plan_notes',upserts:[['note-1','source-version:v1','040103','Revisar numeración','2026-10-22T13:01:00Z','admin',5]],deletes:[]},
  {table:'journal',upserts:[[5,'plan_note','admin','2026-10-22T13:01:00Z','Agregar nota','{}','{}']],deletes:[]}]};
assert.equal((await handle(request(planMeta),env)).status,200);
assert.equal(sql.prepare('SELECT display_title FROM plan_workspace').get().display_title,'Plano principal');
assert.equal(sql.prepare('SELECT note FROM plan_notes').get().note,'Revisar numeración');
const currentColumns=sql.prepare('PRAGMA table_info(current_attributes)').all().map(row=>row.name);
const currentRow=Object.fromEntries(currentColumns.map(name=>[name,null]));
Object.assign(currentRow,{entity_id:'entity-1',country_code:'PE',ubigeo:'040103',land_area:120});
const entityCommit={action:'commit',id:crypto.randomUUID(),revision:5,result:{revision:6},changes:[
  {table:'meta',upserts:[['revision','6']],deletes:[]},
  {table:'entities',upserts:[['entity-1','lote','PE','040103','2026-10-22T13:02:00Z']],deletes:[]},
  {table:'current_attributes',upserts:[currentColumns.map(name=>currentRow[name])],deletes:[]},
  {table:'journal',upserts:[[6,'apply','admin','2026-10-22T13:02:00Z','Activar lote','{}','{}']],deletes:[]}]};
assert.equal((await handle(request(entityCommit),env)).status,200);
assert.equal(sql.prepare('SELECT land_area FROM current_attributes').get().land_area,120);
assert.equal((await handle(request({...payload,id:crypto.randomUUID(),changes:[{table:'master_operations',upserts:[],deletes:[]}]}),env)).status,400);
const vectorRequest=new Request('https://unit.test/v1/vector-object?key=geollaqta%2Fvectores%2F040102%2Flotes.part-0001.json.gz',{headers:{Authorization:'Bearer '+token}});
const vectorResponse=await handle(vectorRequest,env);
assert.equal(vectorResponse.status,200);
assert.equal(await vectorResponse.text(),'vector-data');
assert.equal(vectorResponse.headers.get('Content-Type'),'application/gzip');
assert.equal((await handle(new Request('https://unit.test/v1/vector-object?key=geollaqta%2Fsecret',{headers:{Authorization:'Bearer '+token}}),env)).status,400);
console.log('Private D1 transport: authentication, restricted reads, atomic rollback, CAS, retries and primary-key deletion passed.');
