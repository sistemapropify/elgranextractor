const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/js/catastro-maestro.js'), 'utf8');
assert.match(source, /vectorLayer=new google\.maps\.Data\(\{map\}\)/);
assert.match(source, /vectorLayer\.addGeoJson/);
assert.match(source, /idPropertyName:'MASTER_ID'/);
assert.match(source, /vectorLayer\.setStyle\(vectorStyle\)/);
assert.match(source, /vectorLayer\.overrideStyle/);
assert.doesNotMatch(source, /getContext\('2d'\)/);
assert.doesNotMatch(source, /OverlayView/);
console.log('Master vectors: native Google Maps Data layer verified.');
