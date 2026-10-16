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
