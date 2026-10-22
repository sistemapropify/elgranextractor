/* Private SQL transport for the authenticated Django backend. No browser CORS. */
export const TABLES = {
  meta:['key'],projects:['id'],sources:['id'],versions:['id'],entities:['id'],boundary_segments:['id'],
  contributions:['id'],identities:['version_id','layer','source_feature_id'],
  selections:['entity_id','field'],people:['id'],relationships:['id'],media:['id'],
  registral_acts:['id'],zones:['id'],attribute_definitions:['id'],administrative_areas:['id'],addresses:['id'],property_observations:['id'],
  external_identifiers:['id'],listings:['id'],listing_observations:['id'],transactions:['id'],
  organizations:['id'],activities:['id'],visits:['id'],developments:['id'],
  development_lots:['id'],development_stages:['id'],environment_features:['id'],
  coverage_records:['id'],current_attributes:['entity_id'],journal:['revision']
};
const TABLE_COLUMNS = {
  meta:['key','value'],
  projects:['id','name','country_code','ubigeo','expected_sheets'],
  sources:['id','project_id','name','ubigeo','sheet_code','role'],
  versions:['id','source_id','label','source_date','crs','georeferencing','original_name','original_sha256','digest','created_at','created_by','payload'],
  entities:['id','kind','country_code','ubigeo','created_at'],
  boundary_segments:['id','entity_id','side','length_m','geometry_json','source_version','evidence_json'],
  contributions:['id','version_id','source_feature_id','layer','field','value_json','evidence_json'],
  identities:['version_id','layer','source_feature_id','entity_id'],
  selections:['entity_id','field','contribution_id'],
  people:['id','name','document_type','document_number','source_version'],
  relationships:['id','entity_id','related_entity_id','person_id','kind','details_json','source_version'],
  media:['id','entity_id','kind','object_key','sha256','observed_at','source_version','details_json'],
  registral_acts:['id','entity_id','kind','registry_office','registry_number','registry_seat','observed_at','source_version','details_json'],
  zones:['id','name','kind','revision','geometry_json','rules_json','source_version'],
  attribute_definitions:['id','label','value_type','unit','scope','description','source_version'],
  administrative_areas:['id','parent_id','kind','code','code_scheme','name','valid_from','valid_to','source_version','details_json'],
  addresses:['id','entity_id','target_ref','address_type','full_address','street_type','street_name','municipal_number','interior','postal_code','precision','status','source_version','evidence_json'],
  property_observations:['id','entity_id','target_ref','namespace','field_name','value_type','value_json','unit','method','status','observed_at','valid_from','valid_to','source_version','evidence_json'],
  external_identifiers:['id','entity_id','target_ref','scheme','value','authority','scope','status','observed_at','source_version','evidence_json'],
  listings:['id','entity_id','target_ref','portal','external_id','url','operation','price','currency','area_value','area_unit','area_basis','status','first_seen','last_seen','source_version','details_json'],
  listing_observations:['id','listing_id','observed_at','price','currency','operation','status','details_json','source_version'],
  transactions:['id','entity_id','target_ref','transaction_type','amount','currency','transaction_date','recorded_date','source_version','evidence_json'],
  organizations:['id','name','organization_type','document_type','document_number','source_version','details_json'],
  activities:['id','entity_id','target_ref','organization_id','category','subcategory','activity_name','ciiu_code','ciiu_version','valid_from','valid_to','source_version','evidence_json'],
  visits:['id','entity_id','target_ref','visited_at','observer','summary','source_version','details_json'],
  developments:['id','name','developer_id','status','expected_start','expected_end','source_version','details_json'],
  development_lots:['id','development_id','entity_id','target_ref','role','source_version'],
  development_stages:['id','development_id','name','status','progress','observed_at','source_version','details_json'],
  environment_features:['id','kind','name','ubigeo','geometry_json','source_version','evidence_json'],
  coverage_records:['id','ubigeo','dataset','source_version','complete','record_count','observed_at','details_json'],
  journal:['revision','operation','actor','created_at','reason','details_json','snapshot_json'],
};
const reply=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
async function authorized(request,secret){
  if(!secret)return false;
  const value=request.headers.get('Authorization')||'';
  const encoder=new TextEncoder();
  const [a,b]=await Promise.all([value,'Bearer '+secret].map(s=>crypto.subtle.digest('SHA-256',encoder.encode(s))));
  const av=new Uint8Array(a),bv=new Uint8Array(b);let diff=0;
  for(let i=0;i<av.length;i++)diff|=av[i]^bv[i];return diff===0;
}
function identifier(value){if(!/^[a-z_][a-z0-9_]*$/.test(value))throw Error('Identificador no válido');return '"'+value+'"';}
function validateRead(sql){
  if(typeof sql!=='string'||sql.length>16000||!/^\s*SELECT\b/i.test(sql)||/;|--|\/\*|\b(?:pragma|attach|detach|insert|update|delete|drop|alter|create|load_extension)\b/i.test(sql))throw Error('Consulta no disponible');
}
function chunks(rows,size=100){const result=[];for(let i=0;i<rows.length;i+=size)result.push(rows.slice(i,i+size));return result;}
export async function handle(request,env){
  const url=new URL(request.url);
  if(url.pathname==='/health'&&request.method==='GET')return reply({service:'catastro-maestro',configured:!!(env.DB&&env.MASTER_TOKEN)});
  if(!env.MASTER_TOKEN)return reply({error:'Servicio pendiente de configuración'},503);
  if(!await authorized(request,env.MASTER_TOKEN))return reply({error:'No autorizado'},401);
  if(request.method!=='POST'||url.pathname!=='/v1/database')return reply({error:'Ruta no disponible'},404);
  if(Number(request.headers.get('Content-Length')||0)>12*1024*1024)return reply({error:'Solicitud demasiado grande'},413);
  try{
    const text=await request.text();if(text.length>12*1024*1024)return reply({error:'Solicitud demasiado grande'},413);
    const data=JSON.parse(text);
    if(data.action==='read'){
      if(!Array.isArray(data.queries)||!data.queries.length||data.queries.length>20)throw Error('Lote no válido');
      const statements=data.queries.map(q=>{validateRead(q.sql);if(!Array.isArray(q.params)||q.params.length>90)throw Error('Parámetros no válidos');return env.DB.prepare(q.sql).bind(...q.params);});
      const results=await env.DB.batch(statements);return reply({results:results.map(r=>r.results||[])});
    }
    if(data.action!=='commit')throw Error('Acción no disponible');
    if(!/^[a-f0-9-]{36}$/.test(data.id)||!Number.isSafeInteger(data.revision)||data.revision<0||!Array.isArray(data.changes))throw Error('Cambio no válido');
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify({revision:data.revision,changes:data.changes,result:data.result}))))).map(n=>n.toString(16).padStart(2,'0')).join('');
    const prior=await env.DB.prepare('SELECT digest,result_json FROM master_operations WHERE id=?').bind(data.id).first();
    if(prior){if(prior.digest!==digest)return reply({error:'Operación repetida con contenido diferente'},409);return reply({result:JSON.parse(prior.result_json),replayed:true});}
    const statements=[env.DB.prepare("INSERT INTO master_commit_guard VALUES (1,CASE WHEN (SELECT value FROM meta WHERE key='revision')=? THEN 1 ELSE 0 END)").bind(String(data.revision))];
    const columns={};
    for(const change of data.changes){
      if(!Object.hasOwn(TABLES,change.table)||columns[change.table])throw Error('Tabla no disponible o repetida');
      const names=TABLE_COLUMNS[change.table];
      if(names){columns[change.table]=names;}
      else{
        const info=await env.DB.prepare('PRAGMA table_info('+identifier(change.table)+')').all();
        columns[change.table]=info.results.map(r=>r.name);
      }
      if(!Array.isArray(change.upserts)||!Array.isArray(change.deletes))throw Error('Filas no válidas');
      if(change.upserts.some(row=>!Array.isArray(row)||row.length!==names.length)||change.deletes.some(row=>!Array.isArray(row)||row.length!==TABLES[change.table].length))throw Error('Columnas no válidas');
      if(change.upserts.some(row=>new TextEncoder().encode(JSON.stringify(row)).length>1800000))return reply({error:'Una fila supera el límite D1. Divide la versión de origen.'},413);
    }
    // Child removals precede parents. Parents are inserted before their children.
    const ordered=Object.keys(TABLES);
    for(const table of [...ordered].reverse()){
      const change=data.changes.find(c=>c.table===table);if(!change)continue;
      for(const rows of chunks(change.deletes)){
        const predicate=TABLES[table].map((key,i)=>identifier(table)+'.'+identifier(key)+"=json_extract(j.value,'$["+i+"]')").join(' AND ');
        statements.push(env.DB.prepare('DELETE FROM '+identifier(table)+' WHERE EXISTS(SELECT 1 FROM json_each(?) j WHERE '+predicate+')').bind(JSON.stringify(rows)));
      }
    }
    for(const table of ordered){
      const change=data.changes.find(c=>c.table===table);if(!change)continue;
      const names=columns[table],keys=TABLES[table];
      for(const rows of chunks(change.upserts)){
        const values=names.map((_,i)=>"json_extract(j.value,'$["+i+"]')").join(',');
        const updates=names.filter(n=>!keys.includes(n)).map(n=>identifier(n)+'=excluded.'+identifier(n)).join(',');
        statements.push(env.DB.prepare('INSERT INTO '+identifier(table)+' ('+names.map(identifier).join(',')+') SELECT '+values+' FROM json_each(?) j WHERE 1 ON CONFLICT ('+keys.map(identifier).join(',')+') DO '+(updates?'UPDATE SET '+updates:'NOTHING')).bind(JSON.stringify(rows)));
      }
    }
    statements.push(env.DB.prepare('INSERT INTO master_operations VALUES (?,?,?,?)').bind(data.id,digest,JSON.stringify(data.result),new Date().toISOString()),env.DB.prepare('DELETE FROM master_commit_guard WHERE id=1'));
    // Stay within the currently selected Free plan's 50-query invocation limit.
    if(statements.length+Object.keys(columns).length+2>50)return reply({error:'Divide el cambio en ámbitos menores para el plan D1 actual.'},413);
    try{await env.DB.batch(statements);}catch(error){
      if(String(error.message).includes('CHECK constraint failed'))return reply({error:'La revisión cambió. Vuelve a comparar.'},409);
      // A duplicate operation can have won a concurrent retry.
      const saved=await env.DB.prepare('SELECT digest,result_json FROM master_operations WHERE id=?').bind(data.id).first();
      if(saved&&saved.digest===digest)return reply({result:JSON.parse(saved.result_json),replayed:true});
      return reply({error:'No se pudo confirmar la transacción. Los cambios no se aplicaron.'},502);
    }
    return reply({result:data.result});
  }catch(error){return reply({error:'Solicitud no válida'},400);}
}
export default {fetch:handle};
