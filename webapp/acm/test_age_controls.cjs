const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/static/acm/js/components.js','utf8');
const start=source.indexOf('  function configureType(){'),end=source.indexOf('  async function post(',start);
assert.ok(start>=0&&end>start);
for(const type of ['Casa','Departamento','Oficina','Terreno']){
  for(const age of ['',0,29,30,31,150])for(const built of ['', '0', '200']){
    const fields=Object.fromEntries(['property_type','age','land','built','rooms','baths','floor'].map(k=>[k,{value:k==='property_type'?type:k==='age'?String(age):k==='built'?built:'',disabled:false,required:false}]));
    const nodes=new Map();const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,checked:false,closest(){return this;}});return nodes.get(id);};
    const context={form:{elements:fields},$:node,document:{querySelector:node},map:null,result:null};
    vm.runInNewContext(source.slice(start,end)+';configureType();',context);
    const hidden=type==='Terreno'||type==='Casa'&&age!==''&&Number(age)>=30;
    const soil=hidden||(type==='Casa'&&(built===''||Number(built)===0));
    assert.equal(fields.built.disabled,hidden,`${type}, ${age}: construction field`);
    assert.equal(node('cmp-built-field').hidden,hidden);
    assert.equal(fields.built.required,!hidden&&type!=='Casa');
    assert.equal(node('[name=map_layer][value=land]').checked,soil);
    if(type==='Casa'&&age!==''&&Number(age)>=30)assert.match(node('cmp-method-label').textContent,/30 años o más/);
  }
}
console.log('Age UI: 29/30 boundary, land layer and missing construction, land layer and age boundary verified; apartments and offices retain built area.');
