const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const elements = new Map(), events = [];
class Element {
  constructor(){this.value='';this.checked=false;this.events={};this.style={setProperty(){}};this.classList={toggle(){}};}
  addEventListener(type,callback){this.events[type]=callback;}
  setAttribute(name,value){this[name]=value;}
  append(){}
}
let html='';
const el = selector => {if(!elements.has(selector))elements.set(selector,new Element());return elements.get(selector);};
const host={querySelector(selector){return selector.startsWith('#')&&!html.includes('id="'+selector.slice(1)+'"')?null:el(selector);}};
const sandbox = {window:{ACMPermissions:{adjust_valuation:true,report_notes:true}},
  document:{getElementById:()=>host,createElement:()=>new Element(),dispatchEvent:event=>events.push(event.type)},
  CustomEvent:class {constructor(type){this.type=type;}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'static/acm/js/comparison-valuation.js'),'utf8'),sandbox);
const api=sandbox.window.ACMComparisonValuation;
function mount(params={}){
  elements.clear();html=api.markup(params,{new:{total:100000}});
  el('#cmp-valuation-knob').max='200000';api.mount();
}
mount();
assert.equal(el('#cmp-valuation-amount').value,'','Amount field starts empty');
assert.match(html,/id="cmp-valuation-amount" type="text"/);
assert.match(html,/cmp-valuation-knob/);assert.match(html,/Escribe el valor ajustado/);assert.doesNotMatch(html,/Sin ajuste del agente/);assert.match(html,/Justificación u observaciones/);
el('#cmp-valuation-amount').value='234567.89';el('#cmp-valuation-amount').events.input();
assert.equal(api.value(),234567.89);assert.equal(api.valid(),true);
assert.equal(Number(el('#cmp-valuation-knob').value),234567.89);
assert.ok(Number(el('#cmp-valuation-knob').max)>=234567.89,'Typed value can exceed the original knob range');
el('#cmp-valuation-knob').value='250000';el('#cmp-valuation-knob').events.input();
assert.equal(api.value(),250000);assert.equal(el('#cmp-valuation-amount').value,'','The knob does not prefill the text field');
for(const value of ['-10','1000000001','12.345','abc','0x10']){
  el('#cmp-valuation-amount').value=value;el('#cmp-valuation-amount').events.input();assert.equal(api.valid(),false);
}
el('#cmp-valuation-amount').value='';el('#cmp-valuation-amount').events.input();assert.equal(api.valid(),true);assert.equal(api.value(),null);
el('#cmp-restore-value').events.click();assert.equal(el('#cmp-valuation-amount').value,'');assert.equal(api.valid(),true);assert.equal(api.value(),null);
el('#cmp-report-notes').value='Conservacion buena.\n<script>texto literal</script>';
el('#cmp-report-notes').events.input();assert.equal(api.notes(),el('#cmp-report-notes').value);
const rerender=api.markup({}, {new:{total:100000}});
assert.match(rerender,/&lt;script&gt;texto literal&lt;\/script&gt;/);
assert.doesNotMatch(rerender,/<script>/);
el('#cmp-restore-value').events.click();assert.match(api.notes(),/Conservacion/,'Restore price does not delete justification');
api.reset();mount({manual_valuation:220000.25,report_notes:'Guardado'});
assert.equal(api.value(),220000.25);assert.equal(api.notes(),'Guardado');
api.reset();assert.equal(api.value(),null);assert.equal(api.notes(),'');
sandbox.window.ACMPermissions.adjust_valuation=false;mount();
assert.doesNotMatch(html,/id="cmp-valuation-knob"/);assert.match(html,/id="cmp-report-notes"/);
assert.ok(events.includes('acm:valuation-adjusted'));assert.ok(events.includes('acm:report-notes-changed'));
console.log('Valuation: basic knob, exact typed amount, validation, restore, multiline notes and rerender persistence passed.');

sandbox.window.ACMPermissions={adjust_valuation:true,report_notes:true};api.reset();elements.clear();
html=api.markup({}, {reference_mode:true,new:{total:125000}});el('#cmp-valuation-knob').max='250000';api.mount();
assert.match(html,/Valor por referencias/);assert.match(html,/cmp-valuation-knob/);assert.match(html,/Justificación u observaciones/);
assert.equal(el('#cmp-valuation-amount').value,'');
el('#cmp-valuation-amount').value='140000';el('#cmp-valuation-amount').events.input();
el('#cmp-report-notes').value='Ajuste por conservación.';el('#cmp-report-notes').events.input();
html=api.markup({manual_valuation:api.value()}, {reference_mode:true,new:{total:130000}});
assert.equal(api.value(),140000);assert.equal(api.notes(),'Ajuste por conservación.');
api.reset();elements.clear();html=api.markup({}, {reference_mode:true,new:null});el('#cmp-valuation-knob').max='1000';api.mount();
assert.match(html,/cmp-valuation-knob/);assert.match(html,/cmp-report-notes/);assert.match(html,/cmp-valuation-amount/);
assert.equal(el('#cmp-adjusted-value').textContent,'Sin cálculo disponible');
console.log('Reference controls: empty exact-value input, knob, preserved manual amount/notes and no fabricated automatic zero verified.');

// The breakdown must be visible in the map's valuation footer, including for
// roles that can read valuations but cannot adjust them.
const target={property_type:'Casa',land:150,built:200};
const components={model:'components',property_type:'Casa',land_unit:600,land_count:2,land_radius:1000,
  new:{total:190000,land_value:90000,built_value:100000}};
for(const adjust of [true,false]){
  sandbox.window.ACMPermissions={adjust_valuation:adjust,report_notes:true};api.reset();
  const rendered=api.markup(target,components);
  assert.match(rendered,/Precio estimado del terreno por m²/);
  assert.match(rendered,/Valorización por componentes/);
  assert.match(rendered,/Construcción y mejoras/);
  assert.match(rendered,/2 terreno\(s\) de la zona/);
  assert.match(rendered,/1[.,\s]?000 m/);
  assert.ok(rendered.indexOf('Precio estimado del terreno por m²')<rendered.indexOf('Valorización de la propiedad'));
  assert.ok(rendered.indexOf('Valorización por componentes')<rendered.indexOf('Valorización de la propiedad'));
}
api.reset();
const fallback=api.markup(target,{model:'built',reference_mode:true,land_unit:600,land_count:1,land_radius:500,new:{total:105000}});
assert.match(fallback,/Precio estimado del terreno por m²/);
assert.match(fallback,/Desglose por componentes no disponible/);
assert.doesNotMatch(fallback,/cmp-valuation-components/);
const noSoil=api.markup(target,{model:'built',reference_mode:true,land_unit:null,new:{total:105000}});
assert.match(noSoil,/No disponible/);
assert.doesNotMatch(noSoil,/\$\s*0[.,]00\/m²/);
assert.match(api.markup(target,{...components,new:null}),/Precio estimado del terreno por m²/);
console.log('Soil price, evidence, component breakdown and incomplete/reference calculations verified for both valuation roles.');
for(const type of ['Casa','Departamento','Oficina','Terreno']){
  for(const adjust of [true,false]){
    sandbox.window.ACMPermissions={adjust_valuation:adjust,report_notes:true};api.reset();
    const rendered=api.markup({property_type:type,land:0,built:100},{model:'built',land_unit:null,
      zone_land:{unit:700,count:3,radius:1000,ids:['soil']},new:{total:105000}});
    assert.match(rendered,/Precio estimado del terreno por m²/);
    assert.match(rendered,/700/);
    assert.match(rendered,/3 terreno\(s\) de la zona/);
    assert.ok(rendered.indexOf('Precio estimado del terreno por m²')<rendered.indexOf('Valorización de la propiedad'));
  }
}
assert.match(api.markup({property_type:'Oficina'},{model:'built',zone_land:{unit:700,count:1,radius:500},new:null}),/700/);
assert.match(api.markup({property_type:'Departamento'},{model:'built',zone_land:{unit:null,count:0,radius:2000},new:{total:100000}}),/No disponible/);
console.log('Basic view: independent soil indicator is visible for houses, apartments, offices and land, with and without price-adjustment permission.');
