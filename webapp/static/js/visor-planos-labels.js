(function(root,factory){'use strict';const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;else root.PlanosLabels=api;})(typeof window==='object'?window:globalThis,function(root){
'use strict';
function world(lng,lat){const sin=Math.sin(Math.max(-85.05112878,Math.min(85.05112878,lat))*Math.PI/180);return[(lng+180)/360,.5-Math.log((1+sin)/(1-sin))/(4*Math.PI)];}
function category(name){return /nombre|urban|zona|nom per|a\.h\./i.test(name)?0:/manzan|mza/i.test(name)?1:2;}
function vector(geometry){return ['Polygon','MultiPolygon','LineString','MultiLineString'].includes(geometry.type);}
function prepare(feature){const rings=[],bounds=[Infinity,Infinity,-Infinity,-Infinity];function walk(v){if(typeof v[0]?.[0]==='number'){rings.push(v.map(p=>{const q=world(...p);bounds[0]=Math.min(bounds[0],q[0]);bounds[1]=Math.min(bounds[1],q[1]);bounds[2]=Math.max(bounds[2],q[0]);bounds[3]=Math.max(bounds[3],q[1]);return q;}));}else v.forEach(walk);}walk(feature.geometry.coordinates);return{feature,rings,bounds};}
function create(map){
 const gm=root.google.maps;
 class Labels extends gm.OverlayView{
  constructor(){super();this.rows=[];this.vectors=[];this.cache=new WeakMap();this.layers=new Map();this.opacity=1;this.frame=null;this.setMap(map);}
  onAdd(){this.canvas=root.document.createElement('canvas');this.canvas.style.cssText='position:absolute;pointer-events:none;z-index:5;';this.canvas.setAttribute('aria-label','Plano completo: líneas, números y nombres');this.getPanes().overlayLayer.appendChild(this.canvas);}
  onRemove(){if(this.frame!==null)root.cancelAnimationFrame(this.frame);this.frame=null;this.canvas?.remove();this.canvas=null;}
  setFeatures(features,layers,opacity){this.layers=layers;this.opacity=opacity;this.rows=[];this.vectors=[];for(const f of features){let row=this.cache.get(f);if(vector(f.geometry)){if(!row){row=prepare(f);this.cache.set(f,row);}this.vectors.push(row);}else if(f.geometry.type==='Point'&&f.properties.texto){if(!row){const[x,y]=world(...f.geometry.coordinates);row={feature:f,x,y,kind:category(f.properties.capa),text:String(f.properties.texto).replace(/\s+/g,' ').trim()};this.cache.set(f,row);}this.rows.push(row);}}this.draw();}
  draw(){if(this.frame!==null)return;this.frame=root.requestAnimationFrame(()=>{this.frame=null;this.paint();});}
  paint(){
   const canvas=this.canvas,projection=this.getProjection(),center=map.getCenter(),div=map.getDiv();if(!canvas||!projection||!center||!div.clientWidth||!div.clientHeight)return;
   const width=div.clientWidth,height=div.clientHeight,dpr=Math.min(root.devicePixelRatio||1,2),anchor=projection.fromLatLngToDivPixel(center),scale=projection.getWorldWidth(),[cx,cy]=world(center.lng(),center.lat());
   canvas.style.left=(anchor.x-width/2)+'px';canvas.style.top=(anchor.y-height/2)+'px';canvas.style.width=width+'px';canvas.style.height=height+'px';
   const pw=Math.round(width*dpr),ph=Math.round(height*dpr);if(canvas.width!==pw||canvas.height!==ph){canvas.width=pw;canvas.height=ph;}
   const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);ctx.globalAlpha=this.opacity;ctx.textAlign='center';ctx.textBaseline='middle';
   this.screen={cx,cy,scale,width,height};
   const grouped=new Map();for(const row of this.vectors){const layer=this.layers.get(row.feature.properties.capa);if(!layer?.visible)continue;const[x,y,X,Y]=row.bounds;if(X<cx-width/2/scale||x>cx+width/2/scale||Y<cy-height/2/scale||y>cy+height/2/scale)continue;const name=row.feature.properties.capa;if(!grouped.has(name))grouped.set(name,[]);grouped.get(name).push(row);}
   for(const[name,rows]of grouped){ctx.beginPath();ctx.strokeStyle=this.layers.get(name).color;ctx.lineWidth=/lote|parcel|predio/i.test(name)?1:1.2;for(const row of rows)for(const ring of row.rings)for(let i=0;i<ring.length;i++){const p=ring[i],x=(p[0]-cx)*scale+width/2,y=(p[1]-cy)*scale+height/2;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();}
   const zoom=map.getZoom(),dark=['satellite','hybrid'].includes(map.getMapTypeId()),minZoom=[13,15,17],font=[11,12,10];
   // Data remains complete. Only on-screen labels large enough to be legible
   // are painted; zooming/panning reveals the rest without another import.
   for(let kind=0;kind<3;kind++){if(zoom<minZoom[kind])continue;ctx.font=(kind===1?'600 ':'400 ')+font[kind]+'px Arial,sans-serif';
    for(const row of this.rows){if(row.kind!==kind)continue;const layer=this.layers.get(row.feature.properties.capa);if(!layer?.visible)continue;
     const x=(row.x-cx)*scale+width/2,y=(row.y-cy)*scale+height/2;if(x< -100||y< -20||x>width+100||y>height+20)continue;
     let color=layer.color||'#25364a';if(/^#(?:ffffff|f{3}|808080)$/i.test(color))color=dark?'#ffffff':'#243444';
     ctx.strokeStyle=dark?'#13212d':'#ffffff';ctx.lineWidth=2.5;ctx.strokeText(row.text,x,y);ctx.fillStyle=color;ctx.fillText(row.text,x,y);
    }
   }
   canvas.dataset.loadedLabels=String(this.rows.length);
   canvas.dataset.loadedContours=String(this.vectors.length);
  }
  pick(latLng){const[x,y]=world(latLng.lng(),latLng.lat()),scale=this.screen?.scale;if(!scale)return null;const tolerance=6/scale;for(const row of this.vectors){if(!this.layers.get(row.feature.properties.capa)?.visible)continue;const[a,b,A,B]=row.bounds;if(x<a-tolerance||x>A+tolerance||y<b-tolerance||y>B+tolerance)continue;for(const ring of row.rings)for(let i=1;i<ring.length;i++){const p=ring[i-1],q=ring[i],dx=q[0]-p[0],dy=q[1]-p[1],length=dx*dx+dy*dy,t=length?Math.max(0,Math.min(1,((x-p[0])*dx+(y-p[1])*dy)/length)):0;if(Math.hypot(x-p[0]-t*dx,y-p[1]-t*dy)<=tolerance)return row.feature;}}return null;}
 }
 return new Labels();
}
return{world,category,create};
});
