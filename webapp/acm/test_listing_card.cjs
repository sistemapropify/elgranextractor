const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const presentation = require('./static/acm/js/components-presentation.js');
const source = fs.readFileSync(path.join(__dirname, 'static/acm/js/components.js'), 'utf8');
// Execute the production card heading used by cards and the property detail.
const headingSource = source.slice(source.indexOf('  function heading('), source.indexOf('  function areas('));
assert.ok(headingSource.includes('presentation.offer'));
const sandbox = {presentation, suggestedBadge: () => '', photo: () => '',
  precisionBadge: () => '', publicationBadge: () => '', similarityBlock: () => '',
  escape: value => String(value), money: value => 'USD ' + Math.round(value), excluded: new Set()};
vm.createContext(sandbox);
vm.runInContext(headingSource, sandbox);
const base = {source:'comparable', distance:315, title:'Departamento · Cayma',
  kind:'Departamento', district:'Cayma', operation:'Venta', price:130000, built:65, issues:[]};
const html = sandbox.heading(base, false);
assert.match(html, /Precio de venta total/);
assert.match(html, /USD 130000/);
assert.match(html, /Precio por m² construido: <strong>USD 2000\/m²/);
const land = sandbox.heading({...base, kind:'Terreno', price:100000, land:200}, false);
assert.match(land, /Precio por m² de terreno: <strong>USD 500\/m²/);
const rent = sandbox.heading({...base, operation:'Alquiler', price:756}, false);
assert.match(rent, /Importe de alquiler anunciado/);
assert.doesNotMatch(rent, /Precio de venta total/);
assert.match(rent, /USD 756/);
assert.match(rent, /USD 12\/m²/);
console.log('Production card heading: total and price per m² are both visible; rent is labelled separately.');
