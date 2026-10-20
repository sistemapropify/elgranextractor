const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/static/acm/js/components.js','utf8');
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:true});return nodes.get(id);};
const sent=[],downloads=[];
const sandbox={snapshot:{token:'signed-analysis',params:{}},result:{new:{total:350000}},reportDownloading:false,
  permissions:{adjust_valuation:true,report_notes:true},excluded:new Set(),unselected:new Set(),
  comparisonRows:()=>[{id:'selected-property'}],updateReportButtons(){},$:get,
  form:{elements:{csrfmiddlewaretoken:{value:'csrf'}}},
  window:{ACMComparisonValuation:{valid:()=>true,value:()=>487038.39,notes:()=>'Mejoras y conservacion revisadas.'}},
  document:{createElement:()=>({click(){downloads.push(this.download);}})},
  URL:{createObjectURL:()=>'blob:pdf',revokeObjectURL(){}},setTimeout:fn=>fn(),
  fetch:async(url,options)=>{sent.push(JSON.parse(options.body));return {ok:false,json:async()=>({error:'La búsqueda venció (30 minutos). Busca nuevamente para descargar el informe.'})};}
};
const selection=source.slice(source.indexOf('  function selection(){'),source.indexOf('\n',source.indexOf('  function selection(){')));
const download=source.slice(source.indexOf('  function reportStatus('),source.indexOf("  $('cmp-word').addEventListener"));
vm.runInNewContext(selection+'\n'+download,sandbox);
(async()=>{
  await sandbox.downloadReport('/pdf','.pdf','PDF');
  assert.equal(sent[0].manual_valuation,487038.39);
  assert.equal(sent[0].report_notes,'Mejoras y conservacion revisadas.');
  assert.equal(sent[0].report_ids[0],'selected-property');
  assert.equal(get('cmp-report-status').hidden,false);
  assert.match(get('cmp-report-status').textContent,/búsqueda venció/);
  assert.equal(sandbox.window.ACMComparisonValuation.value(),487038.39);
  assert.equal(sandbox.window.ACMComparisonValuation.notes(),'Mejoras y conservacion revisadas.');
  sandbox.fetch=async()=>({ok:true,headers:{get:()=> 'ACM-test'},blob:async()=>new Uint8Array([37,80,68,70])});
  await sandbox.downloadReport('/pdf','.pdf','PDF');
  assert.deepEqual(downloads,['ACM-test.pdf']);
  assert.equal(get('cmp-report-status').textContent,'Informe PDF descargado.');
  sandbox.reportStatus('');assert.equal(get('cmp-report-status').hidden,true);
  console.log('PDF download: adjusted value and justification sent, errors visible beside download, failed drafts preserved, successful download verified.');
})().catch(error=>{console.error(error);process.exitCode=1;});
