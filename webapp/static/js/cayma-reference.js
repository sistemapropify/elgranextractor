/* Registration is kept separately from immutable source geometry. */
(() => {
    'use strict';
    const source='cayma-pud-2006-eu03',base='/catastro/api/maestro/fuentes/'+source+'/';
    const metre=6371008.8*Math.PI/180;
    const world=([lng,lat])=>{const s=Math.sin(lat*Math.PI/180);return [(lng+180)/360*256,(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*256];};
    const shift=(east,north,lat)=>[east/(metre*Math.cos(lat*Math.PI/180)),north/metre];
    const clone=value=>JSON.parse(JSON.stringify(value));
    const identity=()=>({east_m:0,north_m:0,scale:1});
    function matrix(placement,blockId,pivots,latitude){
        const edit=placement.blocks?.[blockId]||identity(),pivot=pivots.get(blockId)||[0,0],s=edit.scale;
        const delta=shift(placement.east_m+edit.east_m,placement.north_m+edit.north_m,latitude);
        return [s,pivot[0]*(1-s)+delta[0],pivot[1]*(1-s)+delta[1]];
    }
    const point=(p,m)=>[p[0]*m[0]+m[1],p[1]*m[0]+m[2]];
    const box=(b,m)=>[b[0]*m[0]+m[1],b[1]*m[0]+m[2],b[2]*m[0]+m[1],b[3]*m[0]+m[2]];
    function inRing(p,ring){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){
        const a=ring[i],b=ring[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
    }return inside;}
    window.CaymaReferenceMath={world,shift,matrix,point,box,inRing};
    if(typeof document==='undefined')return;
    function init(map){
        const $=id=>document.getElementById('cayma-ref-'+id),panel=document.getElementById('panel-cayma-reference');
        if(!panel||map.__caymaReference)return;map.__caymaReference=true;
        let records=[],blocks=[],pivots=new Map(),saved=null,draft=null,editing=false,marker=null,loading=null,
            canEdit=false,permissionError=null,sourceLat=-16.34800471,selected=null,drag=null,mapOptions=null,saving=false;
        const mapDiv=map.getDiv();
        const blockMode=()=>editing&&$('mode').value==='block';
        const message=(text,error=false)=>{$('status').textContent=text;$('status').dataset.error=String(error);};
        const transform=record=>matrix(draft,record.blockId,pivots,sourceLat);
        function target(create=false){
            if(!blockMode())return draft;
            if(!selected)return null;
            if(create&&!draft.blocks[selected])draft.blocks[selected]=identity();
            return draft.blocks[selected]||identity();
        }
        function offset(){
            const current=target();
            $('offset').textContent=current?'Este: '+current.east_m.toFixed(2)+' m · Norte: '+current.north_m.toFixed(2)+' m':'';
            $('selection').textContent=selected?'Manzana seleccionada · '+records.filter(r=>r.key==='lotes'&&r.blockId===selected).length+' lotes':'Haz clic dentro de una manzana para seleccionarla.';
            $('scale').textContent=Math.round((current?.scale||1)*1000)/10+' %';
            $('reset-block').disabled=!selected||saving;
        }
        async function read(path,options={}){
            const url=path.startsWith('posicion/')?base+path:'/cuadrantizacion/referencias/'+source+'/'+path;
            const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options,headers:{Accept:'application/json',...options.headers}});
            if(response.redirected||!response.headers.get('content-type')?.includes('application/json'))throw Error('La consulta no devolvió la posición local. Recarga o vuelve a intentarlo.');
            const value=await response.json();if(!response.ok){const error=Error(value.error||'No se pudo consultar la fuente.');error.status=response.status;throw error;}return value;
        }
        class Layer extends google.maps.OverlayView{
            onAdd(){this.canvas=document.createElement('canvas');this.canvas.style.cssText='position:absolute;pointer-events:none;z-index:120002';this.getPanes().overlayLayer.append(this.canvas);}
            onRemove(){this.canvas?.remove();}
            draw(){
                if(!this.canvas||!map.getBounds()||!draft)return;this.canvas.hidden=!$('visible').checked;if(this.canvas.hidden)return;
                const w=mapDiv.clientWidth,h=mapDiv.clientHeight,ratio=Math.min(window.devicePixelRatio||1,2),bounds=map.getBounds(),ne=bounds.getNorthEast(),sw=bounds.getSouthWest();
                this.canvas.width=w*ratio;this.canvas.height=h*ratio;this.canvas.style.width=w+'px';this.canvas.style.height=h+'px';
                const nw=new google.maps.LatLng(ne.lat(),sw.lng()),origin=this.getProjection().fromLatLngToDivPixel(nw),start=world([nw.lng(),nw.lat()]),scale=2**map.getZoom();
                this.canvas.style.left=origin.x+'px';this.canvas.style.top=origin.y+'px';
                const ctx=this.canvas.getContext('2d'),matrices=new Map();ctx.scale(ratio,ratio);
                for(const key of ['manzanas','lotes'])for(const highlight of [false,true]){
                    if(!$(key==='lotes'?'lots':'blocks').checked)continue;
                    ctx.beginPath();
                    for(const record of records){
                        if(record.key!==key||(blockMode()&&record.blockId===selected)!==highlight)continue;
                        if(!matrices.has(record.blockId))matrices.set(record.blockId,transform(record));
                        const m=matrices.get(record.blockId),b=box(record.bbox,m);
                        if(b[2]<sw.lng()||b[0]>ne.lng()||b[3]<sw.lat()||b[1]>ne.lat())continue;
                        for(const ring of record.rings){
                            ring.forEach((p,i)=>{const q=world(point(p,m)),x=(q[0]-start[0])*scale,y=(q[1]-start[1])*scale;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.closePath();
                        }
                    }
                    ctx.strokeStyle=highlight?'#54dfff':key==='manzanas'?'#008f6c':'#e3a02b';ctx.lineWidth=highlight?(key==='manzanas'?4:2):key==='manzanas'?2:1;ctx.stroke();
                }
            }
        }
        const overlay=new Layer();overlay.setMap(map);
        function redraw(){offset();overlay.draw();}
        function endDrag(){
            if(drag){const id=drag.id;drag=null;try{mapDiv.releasePointerCapture(id);}catch(_){}}
            mapDiv.style.cursor=blockMode()?'crosshair':'';
        }
        function restoreMap(){if(mapOptions){map.setOptions(mapOptions);mapOptions=null;}mapDiv.style.cursor='';}
        function modeChanged(){
            endDrag();marker?.setMap(null);marker=null;restoreMap();
            $('block-tools').hidden=!blockMode();$('source-help').hidden=blockMode();
            if(blockMode()){
                mapOptions={draggable:map.get('draggable')??true,scrollwheel:map.get('scrollwheel')??null,disableDoubleClickZoom:map.get('disableDoubleClickZoom')??false};
                map.setOptions({draggable:false,scrollwheel:false,disableDoubleClickZoom:true});mapDiv.style.cursor='crosshair';
            }else if(editing){
                marker=new google.maps.Marker({map,position:map.getCenter(),draggable:true,title:'Arrastra para mover todo el plano de Cayma',icon:{path:google.maps.SymbolPath.CIRCLE,scale:11,fillColor:'#f2a431',fillOpacity:1,strokeColor:'#fff',strokeWeight:3}});
                let anchor,start;
                marker.addListener('dragstart',()=>{anchor=marker.getPosition();start=clone(draft);});
                marker.addListener('drag',event=>{if(saving)return;draft.east_m=start.east_m+(event.latLng.lng()-anchor.lng())*metre*Math.cos(sourceLat*Math.PI/180);draft.north_m=start.north_m+(event.latLng.lat()-anchor.lat())*metre;redraw();});
            }
            redraw();
        }
        function stopEdit(){
            endDrag();editing=false;marker?.setMap(null);marker=null;restoreMap();$('editing').hidden=true;
            $('edit').disabled=!records.length||permissionError?.status===403;
            $('edit').textContent=permissionError&&permissionError.status!==403?'Reintentar ajuste':'Ajustar posición';
            $('edit').title=permissionError?.message||'Ajustar todo el plano o cada manzana';
            $('position').textContent='Posición inmovilizada · revisión '+saved.revision;
        }
        async function checkPermission(){try{await read('posicion/');canEdit=true;permissionError=null;}catch(error){canEdit=false;permissionError=error;}}
        function permissionNotice(){if(permissionError)message(permissionError.message+(permissionError.status===403?'':' Pulsa «Reintentar ajuste» para volver a consultar.'),true);}
        function fit(){
            if(!draft||!blocks.length)return;
            const b=[Infinity,Infinity,-Infinity,-Infinity];for(const record of blocks){const v=box(record.bbox,transform(record));b[0]=Math.min(b[0],v[0]);b[1]=Math.min(b[1],v[1]);b[2]=Math.max(b[2],v[2]);b[3]=Math.max(b[3],v[3]);}
            map.fitBounds({west:b[0],south:b[1],east:b[2],north:b[3]},40);
        }
        async function load(fitAfter=false){
            if(loading)return loading;
            message('Cargando manzanas y lotes de Cayma…');
            loading=(async()=>{
                const [lots,blockData]=await Promise.all(['lotes','manzanas'].map(key=>read(key+'/?ubigeo=040103&original=1')));
                if(lots.placement.revision!==blockData.placement.revision)throw Error('La posición cambió durante la carga. Vuelve a activar la capa.');
                saved=clone(lots.placement);saved.blocks||={};draft=clone(saved);selected=null;records=[];pivots=new Map();
                const original=lots.original_bbox||lots.bbox;sourceLat=(original[1]+original[3])/2;
                for(const [data,key] of [[lots,'lotes'],[blockData,'manzanas']])for(const f of data.features){
                    const polys=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates,rings=polys.flat(),bbox=[Infinity,Infinity,-Infinity,-Infinity];
                    for(const ring of rings)for(const p of ring){bbox[0]=Math.min(bbox[0],p[0]);bbox[1]=Math.min(bbox[1],p[1]);bbox[2]=Math.max(bbox[2],p[0]);bbox[3]=Math.max(bbox[3],p[1]);}
                    const blockId=key==='manzanas'?f.id:f.properties.BLOCK_REF;
                    records.push({id:f.id,key,blockId,rings,polys,bbox});
                    if(key==='manzanas')pivots.set(f.id,[(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2]);
                }
                blocks=records.filter(r=>r.key==='manzanas');
                $('lot-count').textContent='('+lots.features.length.toLocaleString('es-PE')+')';$('block-count').textContent='('+blocks.length.toLocaleString('es-PE')+')';
                await checkPermission();stopEdit();redraw();if(fitAfter&&$('visible').checked)fit();
                if(canEdit)message('Fuente lista · sin numeración catastral. Puedes ajustar la posición.');else permissionNotice();
            })().catch(error=>{message(error.message,true);}).finally(()=>{loading=null;});return loading;
        }
        function show(value,focus=false){
            $('visible').checked=value;$('options').hidden=!value;
            if(!value){if(editing){draft=clone(saved);stopEdit();}overlay.draw();return;}
            if(!records.length)load(focus);else{overlay.draw();if(focus)fit();}
        }
        function locationAt(event){
            const rect=mapDiv.getBoundingClientRect(),projection=overlay.getProjection();
            if(!projection)return null;
            const p=projection.fromContainerPixelToLatLng(new google.maps.Point(event.clientX-rect.left,event.clientY-rect.top));
            return p?[p.lng(),p.lat()]:null;
        }
        function hit(p){
            // Test the selected block first when temporarily overlapping its neighbours.
            const candidates=selected?[...blocks.filter(r=>r.id===selected),...blocks.filter(r=>r.id!==selected)]:blocks;
            for(const record of candidates){
                const m=transform(record),b=box(record.bbox,m);if(p[0]<b[0]||p[0]>b[2]||p[1]<b[1]||p[1]>b[3])continue;
                const q=[(p[0]-m[1])/m[0],(p[1]-m[2])/m[0]];
                if(record.polys.some(poly=>inRing(q,poly[0])&&!poly.slice(1).some(ring=>inRing(q,ring))))return record.id;
            }return null;
        }
        const consume=event=>{event.preventDefault();event.stopImmediatePropagation();};
        mapDiv.addEventListener('pointerdown',event=>{
            if(!blockMode()||saving||event.button!==0||event.target?.closest?.('button,input,select,a,#panel-cayma-reference'))return;
            const p=locationAt(event),id=p&&hit(p);if(!id)return;
            consume(event);selected=id;drag={id:event.pointerId,last:p};mapDiv.setPointerCapture(event.pointerId);mapDiv.style.cursor='grabbing';redraw();
        },true);
        mapDiv.addEventListener('pointermove',event=>{
            if(!drag||drag.id!==event.pointerId||saving)return;consume(event);const p=locationAt(event);if(!p)return;
            const edit=target(true);edit.east_m=Math.max(-2000,Math.min(2000,edit.east_m+(p[0]-drag.last[0])*metre*Math.cos(sourceLat*Math.PI/180)));edit.north_m=Math.max(-2000,Math.min(2000,edit.north_m+(p[1]-drag.last[1])*metre));drag.last=p;redraw();
        },true);
        for(const kind of ['pointerup','pointercancel','lostpointercapture'])mapDiv.addEventListener(kind,event=>{if(drag&&event.pointerId===drag.id){consume(event);endDrag();}},true);
        mapDiv.addEventListener('wheel',event=>{
            if(!blockMode()||!selected||saving||event.target?.closest?.('#panel-cayma-reference'))return;
            consume(event);const edit=target(true),pixels=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?mapDiv.clientHeight:1);
            edit.scale=Math.max(.1,Math.min(10,edit.scale*Math.exp(-Math.max(-100,Math.min(100,pixels))*.0015)));redraw();
        },{capture:true,passive:false});
        $('visible').addEventListener('change',()=>show($('visible').checked,true));
        for(const key of ['lots','blocks'])$(key).addEventListener('change',()=>overlay.draw());
        $('fit').addEventListener('click',fit);$('mode').addEventListener('change',modeChanged);
        $('reset-block').addEventListener('click',()=>{if(editing&&selected&&!saving){delete draft.blocks[selected];redraw();}});
        $('edit').addEventListener('click',async()=>{
            if(!saved||!records.length||editing)return;
            if(!canEdit){$('edit').disabled=true;message('Comprobando el acceso al ajuste local…');await checkPermission();stopEdit();if(!canEdit){permissionNotice();return;}}
            editing=true;draft=clone(saved);$('editing').hidden=false;$('edit').disabled=true;$('position').textContent='Ajuste en pantalla · todavía sin guardar';modeChanged();
            message('Selecciona una manzana y arrástrala. La rueda cambia su tamaño, incluso mientras la mueves.');
        });
        panel.querySelectorAll('[data-cayma-move]').forEach(button=>button.addEventListener('click',()=>{
            if(!editing||saving)return;const edit=target(true);if(!edit){message('Primero selecciona una manzana.');return;}
            const [east,north]=button.dataset.caymaMove.split(',').map(Number),step=Number($('step').value);edit.east_m=Math.max(-2000,Math.min(2000,edit.east_m+east*step));edit.north_m=Math.max(-2000,Math.min(2000,edit.north_m+north*step));redraw();
        }));
        $('cancel').addEventListener('click',()=>{if(saving)return;draft=clone(saved);stopEdit();overlay.draw();message('Ajuste cancelado. Se conserva la posición guardada.');});
        $('lock').addEventListener('click',async()=>{
            if(saving||!editing)return;saving=true;endDrag();marker?.setDraggable(false);$('lock').disabled=true;$('cancel').disabled=true;$('mode').disabled=true;message('Guardando las posiciones de las manzanas y sus lotes…');
            try{
                const value=await read('posicion/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':$('csrf').querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({revision:saved.revision,east_m:draft.east_m,north_m:draft.north_m,blocks:draft.blocks,locked:true})});
                saved=value;draft=clone(value);stopEdit();
                try{localStorage.setItem('catastro-source-placement',JSON.stringify({source,revision:value.revision,at:Date.now()}));}catch(_){}
                await load(false);message('Posiciones guardadas e inmovilizadas. Se aplican también al ACM.');
            }catch(error){message(error.message+' El ajuste sigue en pantalla.',true);}finally{saving=false;marker?.setDraggable(true);$('lock').disabled=false;$('cancel').disabled=false;$('mode').disabled=false;offset();}
        });
        const district=document.getElementById('geollaqta-district');district?.addEventListener('change',()=>show(district.value==='040103',district.value==='040103'));
        const initial=new URLSearchParams(location.search).get('catastro');if(initial==='cayma'||initial==='040103')show(true,true);
    }
    window.CaymaReferenceMap={init};
})();
