const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const presentation=require('./static/acm/js/components-presentation.js');
const source=fs.readFileSync(path.join(__dirname,'static/acm/js/components.js'),'utf8');
assert.equal(presentation.comparisonFeatures({kind:'Departamento',floor:0}).floor,'Piso: 0');
assert.equal(presentation.comparisonFeatures({kind:'Departamento',floor_label:'3 y 4'}).floor,'Piso: 3 y 4');
assert.equal(presentation.comparisonFeatures({kind:'Casa',floor:7,parking_has:false}).floor,'');
assert.equal(presentation.comparisonFeatures({kind:'Casa',parking_has:false}).parking,'Cochera: No');
assert.equal(presentation.comparisonFeatures({kind:'Casa',parking_has:null}).parking,'Cochera: Sin información');
assert.equal(presentation.comparisonFeatures({kind:'Casa',parking_has:true}).parking,'Cochera: Sí · tipo sin informar');
assert.equal(presentation.comparisonFeatures({kind:'Casa',parking_has:true,parking_status:'conflict'}).parking,'Cochera: Por confirmar');
assert.equal(presentation.comparisonFeatures({kind:'Terreno',parking_has:true}).parking,'');
const rows=[{id:'1',title:'Departamento',source:'remax',kind:'Departamento',floor_label:'3 y 4',
  age:20,price:200000,land:null,built:120,distance:230,parking_has:true,
  parking_types:['lineal_techada','paralela_no_techada'],url:'https://example.com'}];
const nodes=new Map(), get=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,textContent:'',innerHTML:'',replaceChildren(){}});return nodes.get(id);};
const sandbox={presentation,snapshot:{params:{property_type:'Departamento'},warnings:[]},result:{new:{total:1}},
  permissions:{portal_names:true,publication:true},$:get,comparisonRows:()=>rows,orderedComparisonRows:()=>rows,
  markerNumbers:()=>new Map([['1',1]]),value:()=>({status:'area'}),unselected:new Set(),money:String,decimals:String,
  applySelectedRow(){},updateReportButtons(){},window:{},document:{dispatchEvent(){}},CustomEvent:class{}};
const escapeLine=source.split('\n').find(line=>line.startsWith('  const escape='));
const tableLine=source.split('\n').find(line=>line.startsWith('  function calculationTable('));
const render=source.slice(source.indexOf('  function renderComparison(){'),source.indexOf('  function renderCalculationExplanation(){'));
vm.runInNewContext(escapeLine+'\n'+tableLine+'\n'+render,sandbox);
sandbox.renderComparison();
let markup=get('cmp-comparison-content').innerHTML;
assert.equal((markup.match(/<th>/g)||[]).length,9,'Uses the same number of columns');
assert.match(markup,/20 años · Piso: 3 y 4/);
assert.match(markup,/Cochera: Sí · Lineal techada \+ Paralela no techada/);
assert.match(markup,/<small title=/);
if(process.env.ACM_FEATURE_PREVIEW)fs.writeFileSync(process.env.ACM_FEATURE_PREVIEW,markup);
rows[0]={...rows[0],kind:'Casa',parking_has:false,parking_types:[]};sandbox.snapshot.params.property_type='Casa';
sandbox.renderComparison();markup=get('cmp-comparison-content').innerHTML;
assert.match(markup,/Cochera: No/);assert.doesNotMatch(markup,/Piso:/);
rows[0]={...rows[0],kind:'Departamento',floor_label:'3 <img src=x onerror=alert(1)>'};
sandbox.renderComparison();markup=get('cmp-comparison-content').innerHTML;
assert.doesNotMatch(markup,/<img/);assert.match(markup,/&lt;img/);
console.log('Compact ACM features: unchanged columns, floor zero/multiple levels, parking types, unknown/none, and escaped source text passed.');
