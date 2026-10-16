const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const presentation=require('./static/acm/js/components-presentation.js');
const rows=[{id:'ref',kind:'Departamento',price:100000,built:50,overall_similarity:70},
  {id:'a',kind:'Departamento',price:300000,built:100,overall_similarity:89},
  {id:'b',kind:'Departamento',price:200000,built:100,overall_similarity:90}];
const ordered=[rows[2],rows[1]];
const numbers=presentation.numbering(rows,ordered);
assert.equal(numbers.get('b'),1);assert.equal(numbers.get('a'),2);assert.equal(numbers.get('ref'),3);
assert.equal(presentation.marker(rows[1],{},'land',true),'$3,000/m² - (89%)');
assert.doesNotMatch(presentation.marker(rows[1],{},'price',true),/Exa|Sim|Oferta|Anuncio|Suelo/);
assert.equal(presentation.marker({kind:'Casa',price:300000,built:null},{},'land',true),'—/m²');
const source=fs.readFileSync(path.join(__dirname,'static/acm/js/components.js'),'utf8');
const render=source.slice(source.indexOf('  function renderMap(){'),source.indexOf('  function renderSummary(){'));
const created=[];
const sandbox={map:{},result:{},permissions:{property_pins:true,portal_pins:false},
  clearMap:()=>{created.length=0;},drawCircles(){},visibleMapRows:()=>ordered,markerNumbers:()=>numbers,
  $:id=>id==='cmp-marker-mode'?{value:'unit'}:{},value:()=>({status:'area'}),presentation,
  google:{maps:{SymbolPath:{CIRCLE:0},Point:class{},Size:class{},Marker:class{
    constructor(settings){created.push(settings);}addListener(){}
  }}},markers:[],locatedIds:new Set(),startMapPulses(){},snapshot:{params:{radius:500}},decimals:String};
vm.runInNewContext(render,sandbox);sandbox.renderMap();
assert.deepEqual(created.filter(marker=>marker.clickable!==false).map(marker=>marker.label.text),['1','2']);
assert.deepEqual(created.filter(marker=>marker.clickable===false).map(marker=>marker.label.text),['$2,000/m² - (90%)','$3,000/m² - (89%)']);
sandbox.visibleMapRows=()=>[rows[1]];sandbox.renderMap();
assert.equal(created[0].label.text,'2','Unchecking number 1 does not renumber remaining visible pins');
assert.match(source,/cmp-comparable-number/);
console.log('Map: matching checkbox and pin numbers, compact unit labels and stable numbers after deselection passed.');
