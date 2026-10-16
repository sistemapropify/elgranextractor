/* Number labels reuse the loaded vectors; no network requests or map markers. */
(() => {
    'use strict';
    function position(geometry) {
        const polygons=geometry?.type==='Polygon'?[geometry.coordinates]:geometry?.type==='MultiPolygon'?geometry.coordinates:[];
        let best=null,width=0;
        for(const rings of polygons){
            if(!rings[0]?.length)continue;
            const ys=rings[0].map(p=>p[1]),low=Math.min(...ys),high=Math.max(...ys);
            for(const ratio of [.5,.35,.65]){
                const y=low+(high-low)*ratio,xs=[];
                for(const ring of rings)for(let i=0,j=ring.length-1;i<ring.length;j=i++){
                    const a=ring[j],b=ring[i];
                    if((a[1]>y)!==(b[1]>y))xs.push(a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]));
                }
                xs.sort((a,b)=>a-b);
                for(let i=0;i+1<xs.length;i+=2)if(xs[i+1]-xs[i]>width){width=xs[i+1]-xs[i];best={lat:y,lng:(xs[i]+xs[i+1])/2};}
            }
        }
        return best;
    }
    const code=value=>/^[\w-]{1,12}$/.test(String(value??''))?String(value):'';
    function entries(lots=[],blocks=[]){
        const rows=[],groups=new Map();
        const key=p=>[p.ID_DIST,p.COD_SECT,p.COD_MZNA].join(':');
        for(const feature of lots){
            const p=feature.properties||{},point=position(feature.geometry),text=code(p.COD_LOTE);
            if(!point)continue;
            if(text)rows.push({point,text,kind:'lot'});
            if(code(p.COD_MZNA)){
                const group=groups.get(key(p))||{text:'Mz. '+code(p.COD_MZNA),points:[]};
                group.points.push(point);groups.set(key(p),group);
            }
        }
        for(const feature of blocks){
            const p=feature.properties||{},point=position(feature.geometry);
            if(point&&code(p.COD_MZNA))groups.set(key(p),{text:'Mz. '+code(p.COD_MZNA),points:[point]});
        }
        const labels=[...groups.values()].map(g=>({kind:'block',text:g.text,point:{lat:g.points.reduce((n,p)=>n+p.lat,0)/g.points.length,lng:g.points.reduce((n,p)=>n+p.lng,0)/g.points.length}}));
        return labels.concat(rows);
    }
    function create(map,options={}){
        const canvas=document.createElement('canvas');canvas.setAttribute('aria-hidden','true');
        Object.assign(canvas.style,{position:'absolute',pointerEvents:'none',zIndex:'130002'});
        const overlay=new google.maps.OverlayView();let rows=[],visible=true;
        overlay.onAdd=()=>overlay.getPanes().overlayLayer.appendChild(canvas);
        overlay.onRemove=()=>canvas.remove();
        overlay.draw=()=>{
            const projection=overlay.getProjection(),bounds=map.getBounds(),div=map.getDiv(),zoom=map.getZoom();
            if(!projection||!bounds)return;
            canvas.hidden=!visible||zoom<(options.minZoom??17);if(canvas.hidden)return;
            const ne=bounds.getNorthEast(),sw=bounds.getSouthWest(),origin=projection.fromLatLngToDivPixel(new google.maps.LatLng(ne.lat(),sw.lng()));
            const w=div.clientWidth,h=div.clientHeight,ratio=Math.min(window.devicePixelRatio||1,2);
            canvas.width=w*ratio;canvas.height=h*ratio;canvas.style.width=w+'px';canvas.style.height=h+'px';canvas.style.left=origin.x+'px';canvas.style.top=origin.y+'px';
            const ctx=canvas.getContext('2d');if(!ctx)return;
            ctx.scale(ratio,ratio);ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineJoin='round';
            const occupied=[];let count=0;
            for(const row of rows){
                if(row.kind==='lot'&&zoom<(options.lotMinZoom??18))continue;
                const at=projection.fromLatLngToDivPixel(new google.maps.LatLng(row.point.lat,row.point.lng)),x=at.x-origin.x,y=at.y-origin.y;
                if(x<0||y<0||x>w||y>h)continue;
                const block=row.kind==='block';ctx.font=(block?'700 13':'600 11')+'px Arial, sans-serif';
                const half=ctx.measureText(row.text).width/2+4,box=[x-half,y-9,x+half,y+9];
                if(occupied.some(b=>box[0]<b[2]&&box[2]>b[0]&&box[1]<b[3]&&box[3]>b[1]))continue;
                occupied.push(box);ctx.strokeStyle='rgba(255,255,255,.96)';ctx.lineWidth=4;ctx.strokeText(row.text,x,y);ctx.fillStyle=block?'#1355a6':'#12352f';ctx.fillText(row.text,x,y);
                if(++count>=600)break;
            }
        };
        overlay.setMap(map);
        return {setData(lots,blocks){rows=entries(lots,blocks);overlay.draw();},setVisible(value){visible=value;overlay.draw();}};
    }
    window.GeollaqtaLabels={position,entries,create};
})();
