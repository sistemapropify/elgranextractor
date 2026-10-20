const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'static/acm/js/components.js'),'utf8');
const configure=source.slice(source.indexOf('  function configureType()'),source.indexOf('  async function post('));

for(const basic of [true,false]){
  for(const type of ['Casa','Departamento','Terreno']){
    const nodes=new Map(),selectors=new Map();
    const mode=basic?{value:'unit'}:{value:'land',options:[{},{},{}]};
    nodes.set('cmp-marker-mode',mode);
    const elements=Object.fromEntries(['property_type','age','land','built','rooms','baths','floor'].map(key=>[key,{value:key==='property_type'?type:''}]));
    const context={form:{elements},$:id=>{if(!nodes.has(id))nodes.set(id,{});return nodes.get(id);},map:null,result:null,
      document:{querySelector:selector=>{if(!selectors.has(selector))selectors.set(selector,{closest:()=>({})});return selectors.get(selector);}}};
    vm.runInNewContext(configure+'\nconfigureType();',context);
    assert.equal(elements.property_type.value,type);
    assert.equal(elements.built.disabled,type==='Terreno');
    if(basic)assert.equal(mode.value,'unit','The basic hidden control must remain valid without select.options.');
    else assert.equal(mode.options[1].disabled,type!=='Casa');
  }
}
console.log('Basic card startup: hidden marker control and full selector work for house, apartment and land.');
