(function(root,factory){'use strict';const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PlanosFit=api;})(typeof window==='object'?window:globalThis,function(){
'use strict';
const isLot=name=>/lote|parcela|predio/i.test(name||'');
function bounds(ring){return ring.reduce((b,p)=>[Math.min(b[0],p[0]),Math.min(b[1],p[1]),Math.max(b[2],p[0]),Math.max(b[3],p[1])],[Infinity,Infinity,-Infinity,-Infinity]);}
function insideRing(p,ring){let hit=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
 const a=ring[j],b=ring[i],dx=b[0]-a[0],dy=b[1]-a[1],px=p[0]-a[0],py=p[1]-a[1];
 if(Math.abs(dx*py-dy*px)<1e-12*(dx*dx+dy*dy)&&px*dx+py*dy>=0&&px*dx+py*dy<=dx*dx+dy*dy&&dx*dx+dy*dy>0)return true;
 if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])hit=!hit;
 }return hit;}
function inside(p,polygon){return insideRing(p,polygon.rings[0])&&!polygon.rings.slice(1).some(r=>insideRing(p,r));}
function centroid(ring){const o=ring[0];let sum=0,x=0,y=0;for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length],ax=a[0]-o[0],ay=a[1]-o[1],bx=b[0]-o[0],by=b[1]-o[1],cross=ax*by-bx*ay;sum+=cross;x+=(ax+bx)*cross;y+=(ay+by)*cross;}return sum?[o[0]+x/(3*sum),o[1]+y/(3*sum)]:o;}
// Exact clearance of an axis-aligned text rectangle to every polygon edge.
// In rectangle-scaled coordinates, first contact is the minimum L-infinity
// distance to an edge; concavities and inner rings therefore also constrain it.
function capacity(p,polygon,ratio){let best=Infinity;for(const ring of polygon.rings)for(let i=0;i<ring.length;i++){
 const a=ring[i],b=ring[(i+1)%ring.length],x=(a[0]-p[0])/(ratio/2),y=(a[1]-p[1])/.5,dx=(b[0]-a[0])/(ratio/2),dy=(b[1]-a[1])/.5;
 const candidates=[0,1];for(const[n,d]of [[-x,dx],[-y,dy],[y-x,dx-dy],[-y-x,dx+dy]])if(d){const t=n/d;if(t>0&&t<1)candidates.push(t);}
 for(const t of candidates)best=Math.min(best,Math.max(Math.abs(x+t*dx),Math.abs(y+t*dy)));
 }return best;}
function create(features,project=p=>p){
 const polygons=[],extent=[Infinity,Infinity,-Infinity,-Infinity],grid=new Map(),large=[],cache=new WeakMap();
 for(const feature of features){if(!isLot(feature.properties?.capa))continue;const g=feature.geometry;let shapes=g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:[];
  if(g.type==='LineString'&&g.coordinates.length>3){const a=g.coordinates[0],b=g.coordinates.at(-1);if(a[0]===b[0]&&a[1]===b[1])shapes=[g.coordinates.length?[g.coordinates]:[]];}
  for(const shape of shapes){if(!shape[0]?.length)continue;const rings=shape.map(r=>r.map(p=>project(p))),box=bounds(rings[0]);if(!box.every(Number.isFinite))continue;polygons.push({feature,rings,bounds:box,center:centroid(rings[0])});extent[0]=Math.min(extent[0],box[0]);extent[1]=Math.min(extent[1],box[1]);extent[2]=Math.max(extent[2],box[2]);extent[3]=Math.max(extent[3],box[3]);}
 }
 const sx=128/(extent[2]-extent[0]||1),sy=128/(extent[3]-extent[1]||1),cell=p=>[Math.floor((p[0]-extent[0])*sx),Math.floor((p[1]-extent[1])*sy)];
 for(const polygon of polygons){const b=polygon.bounds,[x,y]=cell(b),[X,Y]=cell(b.slice(2));if((X-x+1)*(Y-y+1)>256){large.push(polygon);continue;}for(let i=x;i<=X;i++)for(let j=y;j<=Y;j++){const key=i+':'+j;if(!grid.has(key))grid.set(key,[]);grid.get(key).push(polygon);}}
 function place(feature,ratio=1.2){let saved=cache.get(feature);if(saved&&saved.ratio===ratio)return saved;const point=project(feature.geometry.coordinates),key=cell(point).join(':');
  const candidates=[...(grid.get(key)||[]),...large].filter(p=>{const b=p.bounds;return point[0]>=b[0]&&point[0]<=b[2]&&point[1]>=b[1]&&point[1]<=b[3]&&inside(point,p);});
  candidates.sort((a,b)=>(a.bounds[2]-a.bounds[0])*(a.bounds[3]-a.bounds[1])-(b.bounds[2]-b.bounds[0])*(b.bounds[3]-b.bounds[1]));
  const polygon=candidates[0];saved={point,capacity:Infinity,polygon:null,ratio};
  if(polygon){const b=polygon.bounds,options=[point,polygon.center,[(b[0]+b[2])/2,(b[1]+b[3])/2]];let best=-1;
   // A small interior grid also finds space in concave or holed lots when the
   // area centroid lies outside. Only first use of a visible label computes it.
   for(let x=1;x<5;x++)for(let y=1;y<5;y++)options.push([b[0]+(b[2]-b[0])*x/5,b[1]+(b[3]-b[1])*y/5]);
   for(const p of options)if(inside(p,polygon)){const room=capacity(p,polygon,ratio);if(room>best){best=room;saved={point:p,capacity:room,polygon,ratio};}}
  }cache.set(feature,saved);return saved;
 }
 return {place,polygons};
}
function fontSize(placement,scale){if(!placement.polygon)return 12;const available=placement.capacity*scale-1/Math.min(placement.ratio/2,.5);return available>=10?Math.min(16,Math.floor(available*2)/2):0;}
return {create,isLot,inside,capacity,fontSize};
});
