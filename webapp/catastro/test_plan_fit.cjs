const assert=require('node:assert/strict'),fit=require('../static/js/visor-planos-fit.js');
const polygon=(coordinates,type='Polygon')=>({geometry:{type,coordinates},properties:{capa:'LOTES'}});
const label=(x,y,text='123')=>({geometry:{type:'Point',coordinates:[x,y]},properties:{capa:'NUMEROS_LOTES',texto:text}});
function contained(placement,size,scale,ratio){
 const[x,y]=placement.point,w=ratio*size/scale/2,h=.5*size/scale;
 for(let i=0;i<=30;i++){const t=i/30;for(const p of [[x-w+2*w*t,y-h],[x-w+2*w*t,y+h],[x-w,y-h+2*h*t],[x+w,y-h+2*h*t]])assert.ok(fit.inside(p,placement.polygon),'Text plus line-height remains inside original polygon');}
}
for(const shape of [
 polygon([[[0,0],[10,0],[10,25],[0,25],[0,0]]]),
 polygon([[[0,0],[12,0],[12,3],[3,3],[3,12],[0,12],[0,0]]]),
 polygon([[[0,0],[20,0],[20,20],[0,20],[0,0]],[[6,6],[6,14],[14,14],[14,6],[6,6]]]),
 polygon([[[0,0],[18,18],[15,21],[-3,3],[0,0]]]),
 polygon([[[[0,0],[10,0],[10,15],[0,15],[0,0]]],[[[30,30],[40,30],[40,40],[30,40],[30,30]]]],'MultiPolygon')
]){
 const point=label(.5,1),layout=fit.create([shape,point]),ratio=2.25,placement=layout.place(point,ratio);
 assert.ok(placement.polygon);assert.ok(fit.inside(placement.point,placement.polygon));
 const size=fit.fontSize(placement,20);assert.ok(size>=10&&size<=16);contained(placement,size,20,ratio);
 assert.equal(fit.fontSize(placement,.05),0,'Do not shrink glyphs below readable size to force them into a distant lot');
 assert.equal(layout.place(point,ratio),placement,'Cache placement while panning/zooming');
}
const small=polygon([[[0,0],[1,0],[1,3],[0,3],[0,0]]]),tiny=label(.5,1);
const placement=fit.create([small,tiny]).place(tiny,1.2);
assert.equal(fit.fontSize(placement,1),0);assert.ok(fit.fontSize(placement,25)>=10);
const original=JSON.stringify(small);fit.create([small,tiny]).place(tiny,1.2);assert.equal(JSON.stringify(small),original,'Original coordinates remain untouched');
assert.equal(fit.create([small]).place(label(50,50)).polygon,null,'Never assign an outside number to an arbitrary neighbouring property');
console.log('Parcel label fitting: narrow, rotated, concave, holed and multipart lots; exact containment, readable zoom and unchanged coordinates passed.');
