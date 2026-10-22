import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {handle} from './worker.mjs';
const sql=new DatabaseSync(':memory:');sql.exec(readFileSync(new URL('schema.sql',import.meta.url),'utf8'));
const DB={prepare(query){let values=[];return {bind(...args){values=args;return this;},async all(){return {results:sql.prepare(query).all(...values)};},async first(){return sql.prepare(query).get(...values)||null;},_run(){const statement=sql.prepare(query);return {results:statement.columns().length?statement.all(...values):(statement.run(...values),[])};}};},async batch(statements){sql.exec('BEGIN');try{const results=statements.map(s=>s._run());sql.exec('COMMIT');return results;}catch(e){sql.exec('ROLLBACK');throw e;}}};
const token='test-only-'.repeat(8),env={DB,MASTER_TOKEN:token};
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
assert.equal((await handle(request({...payload,id:crypto.randomUUID(),changes:[{table:'master_operations',upserts:[],deletes:[]}]}),env)).status,400);
console.log('Private D1 transport: authentication, restricted reads, atomic rollback, CAS, retries and primary-key deletion passed.');
