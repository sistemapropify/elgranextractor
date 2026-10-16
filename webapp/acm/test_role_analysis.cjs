const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'static/acm/js/components.js'),'utf8');
const listeners={},hidden=[];
const form={addEventListener:(type,callback)=>listeners[type]=callback,querySelector:()=>hidden[0],append:node=>hidden.push(node)};
const payload={token:'encrypted-fixture',excluded:['opaque-a'],report_notes:'Nota',manual_valuation:234567.89};
const submit={snapshot:{},result:{},map:{getCenter:()=>({lat:()=>-16.4,lng:()=>-71.5}),getZoom:()=>17},
  unselected:new Set(['opaque-b']),selection:()=>({...payload}),window:{ACMComparisonValuation:{valid:()=>true}},
  $:id=>id==='acm-perspective-form'?form:{},document:{createElement:()=>({}),querySelectorAll:()=>[{value:'property'}]}};
vm.runInNewContext(source.slice(source.indexOf('  const perspectiveForm='),source.indexOf('  function setReportMenu(')),submit);
listeners.submit({preventDefault(){throw Error('Valid analysis must be submitted');}});
const carried=JSON.parse(hidden[0].value);
assert.equal(carried.manual_valuation,234567.89);assert.equal(carried.report_notes,'Nota');
assert.deepEqual(carried.ui.hidden_ids,['opaque-b']);assert.equal(carried.ui.viewport.zoom,17);
const resultData={snapshot:{params:{property_type:'Casa',lat:-16.4,lng:-71.5,land:150,built:200,radius:500},records:[],result:{new:{total:234567.89}}},
  excluded:['opaque-a'],ui:{hidden_ids:['opaque-b'],layers:['property'],viewport:{lat:-16.4,lng:-71.5,zoom:17}}};
const nodes={'cmp-role-analysis-data':{textContent:JSON.stringify(resultData)},'cmp-address':{},'cmp-radius-label':{},'cmp-status':{}};
const fields={};for(const name of ['property_type','age','lat','lng','land','built','rooms','baths','floor','radius','max_radius'])fields[name]={};
const renders=[],layer={value:'property',checked:false};
const resume={$:id=>nodes[id],form:{elements:fields},configureType(){},excluded:new Set(),unselected:new Set(),
  document:{querySelectorAll:()=>[layer]},setLocationLocked(){},setSearchFormCollapsed(){},render:value=>renders.push(value)};
vm.runInNewContext(source.slice(source.indexOf('  const roleAnalysisNode='),source.lastIndexOf('})();')),resume);
assert.deepEqual(renders,[false],'Restoring role results must not request AI explanations');
assert.equal(resume.snapshot.result.new.total,234567.89);assert.equal(resume.unselected.has('opaque-b'),true);
assert.equal(fields.land.value,150);assert.equal(resume.restoredViewport.zoom,17);
assert.equal(layer.checked,true);
assert.doesNotMatch(source.slice(source.indexOf('  const roleAnalysisNode=')),/search-completed|post\('buscar'/);
console.log('Role switching carries the current analysis and restores results without searching or triggering nearby calculations.');
