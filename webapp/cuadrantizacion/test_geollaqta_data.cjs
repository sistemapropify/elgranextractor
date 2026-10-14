const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const sandbox={window:{},URLSearchParams,AbortController,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/geollaqta-data.js'),'utf8'),sandbox);
const api=sandbox.window.GeollaqtaData;
const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'geollaqta_districts.json'),'utf8'));
const reply=data=>({ok:true,redirected:false,headers:{get:()=> 'application/json'},json:async()=>data});
async function main(){
 for(const entry of catalog.districts.filter(d=>d.sample_lot)){
  const requests=[];
  const fetcher=async(url,options)=>{requests.push({url,options});
   if(url.includes('cobertura'))return reply({ubigeo:entry.ubigeo,transport:'browser'});
   return reply(options.body.get('returnIdsOnly')==='true'?{objectIds:[1,2]}:{features:[entry.ubigeo,'150101'].map((code,index)=>({attributes:{OBJECTID:index+1,ID_DIST:code,ID_LOTE:entry.sample_lot},geometry:{rings:[[[-71.5,-16.4],[-71.499,-16.4],[-71.499,-16.399],[-71.5,-16.4]]]}}))});
  };
  const client=api.createClient({district:entry.ubigeo,fetch:fetcher});
  await client.coverage();assert.match(requests[0].url,new RegExp('ubigeo='+entry.ubigeo));assert.match(requests[0].url,/metadata=1/);
  const info={ubigeo:entry.ubigeo,district:entry.name,transport:'browser',service_base:'https://example.test/MapServer',layers:{lotes:{id:10,fields:'OBJECTID,ID_DIST,ID_LOTE',kind:'polygon',name:'Lotes'}}};
  const data=await client.layer(info,'lotes','-71.51,-16.41,-71.49,-16.39');
  assert.equal(data.features.length,1,'Foreign districts excluded');
  assert.equal(requests[1].options.body.get('where'),"ID_DIST='"+entry.ubigeo+"'");
  assert.equal(requests[1].options.credentials,'omit');
  assert.equal(data.features[0].geometry.type,'Polygon');
  const before=requests.length;const detail=await client.detail(data.features[0],info);
  assert.equal(requests.length,before,'Click metadata uses loaded vector without another request');
  assert.equal(detail.properties.ID_LOTE,entry.sample_lot);
  assert.ok(api.facadeUrl(entry.sample_lot).includes('/'+entry.ubigeo+'/'));
  await assert.rejects(client.detail({id:1,properties:{ID_LOTE:'15010112345678'}},info),/distrito/);
 }
 assert.throws(()=>api.createClient({district:"040126' OR 1=1",fetch:()=>{}}),/distrito/i);
 console.log('Map-independent GeoJSON, district filtering, immediate lot detail and facade paths passed for all 10 published districts.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
