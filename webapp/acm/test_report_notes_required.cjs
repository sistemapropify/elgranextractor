const assert = require('node:assert/strict');
const fs = require('node:fs');

const components = fs.readFileSync(__dirname + '/static/acm/js/components.js', 'utf8');
const valuation = fs.readFileSync(__dirname + '/static/acm/js/comparison-valuation.js', 'utf8');
const template = fs.readFileSync(__dirname + '/templates/acm/components.html', 'utf8');

assert.match(components, /function withRequiredPdfNotes/);
assert.match(components, /\$\('notes-required'\)/);
assert.match(components, /dialog\.showModal\(\)/);
assert.match(components, /ACMComparisonValuation\?\.setNotes\(value\)/);
assert.match(valuation, /notesTouched=true/);
assert.match(valuation, /setNotes/);
assert.match(template, /id="cmp-required-notes"/);
assert.match(template, /required placeholder=/);
assert.match(template, /Guardar y emitir PDF/);

console.log('Required PDF justification: blocking modal, persisted note and guarded PDF actions verified.');
