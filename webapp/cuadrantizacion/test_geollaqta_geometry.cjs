const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const sandbox = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/geollaqta-map.js'), 'utf8'), sandbox);
const relation = sandbox.window.GeollaqtaMap.relation;
const ring = (x, y, s) => [[x,y],[x+s,y],[x+s,y+s],[x,y+s],[x,y]];
const polygon = (x, y, s) => ({type: 'Polygon', coordinates: [ring(x,y,s)]});
assert.equal(relation(polygon(2,2,2), ring(0,0,10)), 'Dentro');
assert.equal(relation(polygon(20,20,2), ring(0,0,10)), null);
assert.equal(relation(polygon(9,9,2), ring(0,0,10)), 'Intersecta / toca');
assert.equal(relation(polygon(10,2,2), ring(0,0,10)), 'Intersecta / toca');
assert.equal(relation(polygon(0,0,10), ring(2,2,2)), 'Intersecta / toca');
assert.equal(relation({type:'Polygon',coordinates:[ring(0,0,10),ring(2,2,6)]}, ring(3,3,1)), null);
assert.equal(relation({type:'MultiPolygon',coordinates:[[ring(2,2,1)],[ring(20,20,1)]]},ring(0,0,10)), 'Intersecta / toca');
// Edge crossings with no contained vertices.
assert.equal(relation({type:'Polygon',coordinates:[[[0,4],[10,4],[10,6],[0,6],[0,4]]]}, [[4,0],[6,0],[6,10],[4,10],[4,0]]), 'Intersecta / toca');
console.log('8 cadastral / quadrant geometry cases passed.');
const convert=sandbox.window.GeollaqtaMap.esriGeometry;
assert.deepEqual(JSON.parse(JSON.stringify(convert({rings:[ring(0,0,10),ring(2,2,6),ring(3,3,1),ring(20,20,2)]},'polygon'))),
    {type:'MultiPolygon',coordinates:[[ring(0,0,10),ring(2,2,6)],[ring(20,20,2)],[ring(3,3,1)]]});
assert.equal(convert({paths:[[[0,0],[1,1]]]},'line').type,'LineString');
assert.equal(convert({x:1,y:2},'point').type,'Point');
assert.throws(()=>convert({rings:[[[NaN,0],[1,0],[1,1]]]},'polygon'));
console.log('4 browser transport geometry cases passed.');
