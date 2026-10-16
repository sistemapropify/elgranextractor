const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const texts=[],canvas={style:{},setAttribute(){},getContext:()=>({scale(){},measureText:text=>({width:text.length*6}),strokeText(){},fillText:(text,x,y)=>texts.push({text,x,y})})};
let overlay,zoom=18;
const map={getZoom:()=>zoom,getDiv:()=>({clientWidth:800,clientHeight:600}),getBounds:()=>({getNorthEast:()=>({lat:()=>6,lng:()=>8}),getSouthWest:()=>({lat:()=>0,lng:()=>0})})};
class OverlayView{
 constructor(){overlay=this;}
 getProjection(){return {fromLatLngToDivPixel:p=>({x:p.lng*100,y:(6-p.lat)*100})};}
 getPanes(){return {overlayLayer:{appendChild(){}}};}
 setMap(){this.onAdd();this.draw();}
}
const sandbox={window:{},document:{createElement:()=>canvas},google:{maps:{OverlayView,LatLng:class {constructor(lat,lng){this.lat=lat;this.lng=lng;}}}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/geollaqta-labels.js'),'utf8'),sandbox);
const labels=sandbox.window.GeollaqtaLabels,rectangle=(x,y)=>({type:'Polygon',coordinates:[[[x,y],[x+1,y],[x+1,y+1],[x,y+1],[x,y]]]});
const feature=(lot,x)=>({properties:{ID_DIST:'040126',COD_SECT:'07',COD_MZNA:'038',COD_LOTE:lot},geometry:rectangle(x,2)});
const lot1=feature('027',1),lot2=feature('028',5);
assert.deepEqual(JSON.parse(JSON.stringify(labels.position(rectangle(1,2)))),{lat:2.5,lng:1.5});
const holed={type:'Polygon',coordinates:[[[0,0],[10,0],[10,10],[0,10],[0,0]],[[2,2],[8,2],[8,8],[2,8],[2,2]]]};
const at=labels.position(holed);assert.ok(at.lng<2||at.lng>8,'Label remains outside a polygon hole');
const items=labels.entries([lot1,lot2]);assert.equal(items.length,3);assert.equal(items[0].text,'Mz. 038');
assert.equal(items.filter(r=>r.kind==='block').length,1,'One block number per sector/block');
assert.equal(labels.entries([{...lot1,properties:{}}]).length,0,'Missing codes are not invented');
const numbers=labels.create(map);numbers.setData([lot1,lot2],[]);
assert.deepEqual(texts.map(r=>r.text),['Mz. 038','027','028']);
texts.length=0;zoom=17;overlay.draw();assert.deepEqual(texts.map(r=>r.text),['Mz. 038']);
zoom=16;overlay.draw();assert.equal(canvas.hidden,true,'Hide labels at district overview');
numbers.setVisible(false);zoom=19;overlay.draw();assert.equal(canvas.hidden,true);
texts.length=0;numbers.setVisible(true);assert.equal(canvas.hidden,false);assert.equal(texts.length,3);
assert.equal(canvas.style.pointerEvents,'none','Lot selection remains available under the text');
console.log('Cadastral numbers: real codes, block grouping, hole-safe positions, zoom and visibility passed.');
