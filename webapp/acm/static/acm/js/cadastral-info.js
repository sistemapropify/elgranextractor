(() => {
    'use strict';
    function init(map) {
        const $=id=>document.getElementById('cmp-cadastral'+(id?'-'+id:'')),card=$('');
        if (!card||map.__acmCadastral||!window.ACMPermissions?.cadastral_info) return;
        map.__acmCadastral=true;
        const streetFacade=window.ACMStreetFacade?.create(map);
        const spatial=window.CatastroMasterData,cache=new Map(),layer=new google.maps.Data(),labels=window.GeollaqtaLabels?.create(map,{minZoom:0,lotMinZoom:0});
        let provider=null,providerPromise=null,result=null,lot=null,target=null,serial=0,controller=null,areaController=null,timer=null,drawnKey=null,drawnCount=0,drawnBlockCount=0,highlighted=null,detailsId=null,allowed=true,areaLoading=false,areaEpoch=0,detailLoading=false,photoLookup=null;
        let sourceVersions=null,revisionTimer=null,checkingRevision=false;
        const versions=value=>JSON.stringify(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)));
        function scheduleRevisionCheck(){
            if(!revisionTimer&&allowed&&target&&!document.hidden)revisionTimer=setTimeout(checkRevision,15000);
        }
        function reloadGeometry(){
            const closed=card.hidden;
            ++areaEpoch;areaController?.abort();provider=null;providerPromise=null;result=null;clearMap();cache.clear();
            if(target)queue(target,true);
            if(closed)card.hidden=true;
        }
        async function checkRevision(){
            clearTimeout(revisionTimer);revisionTimer=null;
            if(checkingRevision||!allowed||!target||document.hidden||areaLoading
                ||(result&&!result.complete))return;
            if(sourceVersions===null){scheduleRevisionCheck();return;}
            checkingRevision=true;
            try{
                const value=await api('revisiones/');
                if(!value.sources||typeof value.sources!=='object')return;
                const next=versions(value.sources);
                if(next!==sourceVersions){sourceVersions=next;reloadGeometry();}
            }catch(_){/* Keep the current view and retry; api still enforces revoked access. */}
            finally{checkingRevision=false;scheduleRevisionCheck();}
        }
        layer.setStyle(feature=>({clickable:false,fillColor:'#19b9b0',fillOpacity:feature.getProperty('MASTER_LAYER')==='manzanas'?0:.06,
            strokeColor:feature.getProperty('MASTER_LAYER')==='manzanas'?'#008f6c':feature.getProperty('REFERENCE_ONLY')?'#d69822':'#0caaa2',
            strokeOpacity:.95,strokeWeight:feature.getProperty('MASTER_LAYER')==='manzanas'?2:1.6,zIndex:feature.getProperty('MASTER_LAYER')==='manzanas'?110001:110000}));
        const sides=['frente','derecha','izquierda','fondo'];
        function pdfLink(value){
            const link=$('pdf');if(!link)return;
            link.hidden=true;link.removeAttribute('href');
            if(!window.ACMPermissions?.cadastral_pdf||!value?.selected_record_id||value.document_status==='unavailable')return;
            link.setAttribute('href','/acm/catastro/lotes/'+encodeURIComponent(value.lot_id)+'/reporte.pdf?record_id='+encodeURIComponent(value.selected_record_id));
            link.hidden=false;
        }
        function status(text,error=false){$('status').textContent=text;$('status').hidden=!text;$('status').dataset.error=String(error);}
        function clearFields(){
            if(photoLookup)clearTimeout(photoLookup.timer);photoLookup=null;
            ['code','address','year','floors','units'].forEach(k=>$(k).textContent=k==='code'?'Sin lote seleccionado':'Sin dato');
            if($('source'))$('source').textContent='Sin dato';
            if($('adjust'))$('adjust').hidden=true;
            ['land','built',...sides].forEach(k=>$(k).textContent='Sin dato');
            $('photo').hidden=true;$('photo').removeAttribute('src');$('photo-status').hidden=false;$('photo-status').textContent='Sin fachada disponible';
            $('report-label').hidden=true;$('report').replaceChildren();
            pdfLink();
        }
        function clearMap(){layer.forEach(f=>layer.remove(f));layer.setMap(null);labels?.setData([],[]);drawnKey=null;drawnCount=0;drawnBlockCount=0;highlighted=null;}
        async function api(path,signal){
            const stop=new AbortController(),abort=()=>stop.abort(),deadline=setTimeout(abort,path.startsWith('lotes/')?30000:25000);
            signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
            try {
                const r=await fetch('/acm/catastro/'+path,{credentials:'same-origin',cache:'no-store',signal:stop.signal,headers:{Accept:'application/json'}});
                if(!r.headers.get('content-type')?.includes('application/json'))throw Error('Inicia sesión para consultar el catastro.');
                const data=await r.json();if(!r.ok){if(r.status===401||r.status===403){allowed=false;++serial;clearTimeout(timer);clearMap();clearFields();areaController?.abort();streetFacade?.destroy();result=null;lot=null;cache.clear();card.hidden=true;card.setAttribute('aria-busy','false');}throw Error(data.error||'No se pudo consultar el catastro.');}return data;
            } finally {clearTimeout(deadline);signal?.removeEventListener('abort',abort);}
        }
        function highlight(){
            if(highlighted)layer.revertStyle(highlighted);
            highlighted=lot?layer.getFeatureById(lot.id):null;
            if(highlighted)layer.overrideStyle(highlighted,{fillColor:'#ffa347',fillOpacity:.27,strokeColor:'#ffae56',strokeWeight:2.6});
        }
        function draw(){
            if(!result){clearMap();return;}
            if(!result.complete&&!result.lots.features.length)return;
            if(drawnKey!==result.key){clearMap();drawnKey=result.key;}
            if(drawnCount<result.lots.features.length){layer.addGeoJson({type:'FeatureCollection',features:result.lots.features.slice(drawnCount)});drawnCount=result.lots.features.length;labels?.setData(result.lots.features,[]);}
            const blocks=result.blocks?.features||[];
            if(drawnBlockCount<blocks.length){layer.addGeoJson({type:'FeatureCollection',features:blocks.slice(drawnBlockCount)});drawnBlockCount=blocks.length;}
            layer.setMap(map);highlight();
        }
        function select(){
            const selected=result&&target?spatial.selectedLot(result,target):null;
            lot=selected;highlight();if(!lot){if(detailsId){detailsId=null;clearFields();}return;}
            const p=lot.properties;
            if(p.REFERENCE_ONLY){
                const id=spatial.featureIdentity(lot);
                if(detailsId!==id){controller?.abort();controller=new AbortController();clearFields();detailsId=id;detailLoading=false;}
                $('code').textContent='Sin código catastral en la fuente';$('address').textContent='Sin numeración de manzana / lote';
                if($('source'))$('source').textContent=p.SOURCE_NAME||'Plano municipal de Cayma · 2006';
                if($('adjust'))$('adjust').hidden=false;
                $('hint').textContent='Cayma · contorno recuperado del plano de 2006';
                status('Geometría de referencia; ubicación provisional y numeración pendiente.');$('retry').hidden=true;return;
            }
            if($('source'))$('source').textContent='GeoLlaqta · COFOPRI';
            $('code').textContent=p.ID_LOTE;$('address').textContent=p.COD_SECT+' / '+p.COD_MZNA+' / '+String(p.COD_LOTE??'').padStart(3,'0');
            const year=Number(p.ANIO_CAT);$('year').textContent=Number.isInteger(year)&&year>=1900&&year<=2100?String(year):'Sin dato';
            $('hint').textContent=(p.DISTRICT_NAME||result.district)+' · lote '+p.COD_LOTE;
            if(detailsId!==p.ID_LOTE){detailsId=p.ID_LOTE;['land','built','floors','units',...sides].forEach(k=>$(k).textContent='Cargando…');photo(null,serial);details(serial);}
        }
        function progress(value){
            result=value;draw();select();
            if(!lot)$('hint').textContent='Radio de '+result.radius+' m';
            if(!result.complete&&!lot)status('Cargando catastro…');
            if(result.complete)finish();
        }
        function photo(url,stamp){
            const image=$('photo'),id=lot?.properties.ID_LOTE;
            if(!id)return;
            if(photoLookup?.id===id&&photoLookup.stamp===stamp){
                if(!url||photoLookup.urls.includes(url)||photoLookup.loaded)return;
                // A verified archive image can arrive after source candidates failed.
            }
            if(photoLookup)clearTimeout(photoLookup.timer);
            const urls=[...new Set([url,...Array.from({length:12},(_,index)=>window.GeollaqtaData.facadeUrl(id,index))].filter(Boolean))];
            const lookup=photoLookup={id,stamp,urls,timer:null,loaded:false};let next=0;
            const current=()=>photoLookup===lookup&&stamp===serial&&lot?.properties.ID_LOTE===id;
            $('photo-status').textContent='Cargando fachada…';$('photo-status').hidden=false;
            function attempt(){
                clearTimeout(lookup.timer);if(!current())return;
                if(next>=urls.length){image.hidden=true;$('photo-status').hidden=false;$('photo-status').textContent='Sin fachada disponible';return;}
                const candidate=urls[next++],active=()=>current()&&(image.getAttribute?.('src')??image.src)===candidate;
                image.onload=()=>{if(!active())return;clearTimeout(lookup.timer);lookup.loaded=true;image.hidden=false;$('photo-status').hidden=true;};
                image.onerror=()=>{if(active())attempt();};
                lookup.timer=setTimeout(attempt,6000);image.loading='eager';image.src=candidate;
            }
            attempt();
        }
        function metrics(value,stamp){
            pdfLink(value);
            const data=value.metrics||{};
            $('land').textContent=data.land_area??'Sin dato';$('built').textContent=data.built_area??'Sin dato';
            $('floors').textContent=data.floors??'Sin dato';$('units').textContent=data.units??'Sin dato';
            sides.forEach(k=>$(k).textContent=data.boundaries?.[k]??'Sin dato');
            $('report').replaceChildren();
            (value.reports||[]).forEach(r=>{const o=document.createElement('option');o.value=r.record_id;o.textContent='Reporte '+(r.form_number||r.record_id);$('report').append(o);});
            $('report').value=value.selected_record_id||'';$('report-label').hidden=(value.reports||[]).length<2;
            photo(value.facade_url,stamp);
            if(value.document_status==='unavailable'){
                ['land','built','floors','units',...sides].forEach(k=>$(k).textContent='Consulta no disponible');
                status('No se pudo consultar el documento. Vuelve a intentarlo.',true);$('retry').hidden=false;
            }else status('');
        }
        async function details(stamp,record=''){
            if(!lot||lot.properties.REFERENCE_ONLY)return;
            pdfLink();
            detailLoading=true;
            const id=lot.properties.ID_LOTE,key=id+':'+record;
            try {
                const saved=cache.get(key),value=saved&&saved.until>Date.now()?saved.data:await api('lotes/'+id+'/'+(record?'?record_id='+encodeURIComponent(record):''),controller.signal);
                if(stamp!==serial||lot?.properties.ID_LOTE!==id)return;
                if(value.lot_id!==id)throw Error('La información recibida no corresponde al lote del pin.');
                if(value.document_status!=='unavailable')cache.set(key,{data:value,until:Date.now()+60000});if(cache.size>30)cache.delete(cache.keys().next().value);
                metrics(value,stamp);
            } catch(error){if(stamp===serial&&lot?.properties.ID_LOTE===id){['land','built','floors','units',...sides].forEach(k=>$(k).textContent='Consulta no disponible');status(error.name==='AbortError'?'La consulta tardó demasiado. Vuelve a consultar.':error.message||'No se pudieron consultar los datos catastrales.',true);$('retry').hidden=false;}}
            finally {if(stamp===serial){detailLoading=false;card.setAttribute('aria-busy',String(!!result&&!result.complete));}}
        }
        function finish(){
            if(!result.total)status('No hay lotes publicados dentro de este radio.');
            else if(lot?.properties.REFERENCE_ONLY)status('Cayma · plano de 2006 · ajuste guardado '+(lot.properties.PLACEMENT_REVISION??0)+'. Geometría de referencia; numeración pendiente de contraste.');
            else if(!lot)status('El pin no está dentro de un lote.');
            else if($('retry').hidden)status('');
            card.setAttribute('aria-busy',String(detailLoading));
        }
        async function update(center,radius,epoch,signal){
            try{
                if(!provider){if(!providerPromise)providerPromise=api('configuracion/').then(data=>{
                    if(epoch!==areaEpoch)return;
                    sourceVersions=versions(Object.fromEntries(data.providers.filter(p=>p.active&&p.transport==='master').map(p=>[p.id,p.placement?.revision??0])));
                    provider=spatial.create(data);
                }).finally(()=>{providerPromise=null;});await providerPromise;}
                if(epoch!==areaEpoch||!allowed)return;
                const loaded=await provider.loadRadius(center,radius,{signal,onBatch:(_,data)=>{if(allowed&&epoch===areaEpoch)progress(data);}});
                if(epoch!==areaEpoch)return;result=loaded;draw();select();finish();
            }catch(error){if(epoch===areaEpoch){
                status(error.name==='AbortError'?'La consulta se interrumpió.':error.message,true);
                $('retry').hidden=false;card.setAttribute('aria-busy','false');
            }}finally{if(epoch===areaEpoch)areaLoading=false;}
        }
        function queue(value,force=false){
            if(!allowed)return;
            const location=spatial.point(value);if(!location)return;
            const form=document.getElementById('cmp-form'),radius=Number(form.elements.radius.value),reuse=spatial.covers(result,location,radius);
            target=location;scheduleRevisionCheck();card.hidden=false;if(!$('content').hidden)streetFacade?.queue(location);
            if(reuse&&result.complete&&areaLoading){areaController?.abort();clearTimeout(timer);++areaEpoch;areaLoading=false;}
            const selected=reuse?spatial.selectedLot(result,location):null;
            if(reuse&&!force&&selected&&spatial.featureIdentity(selected)===detailsId){lot=selected;highlight();return;}
            ++serial;controller?.abort();controller=new AbortController();detailLoading=false;lot=null;detailsId=null;clearFields();highlight();
            if(reuse&&!force){if(result.complete||areaLoading)$('retry').hidden=true;select();if(result.complete)finish();return;}
            $('retry').hidden=true;
            areaController?.abort();areaController=new AbortController();clearTimeout(timer);const epoch=++areaEpoch;areaLoading=true;
            // Retry the same footprint; leaving it creates a new circle around the pin.
            const center=reuse?result.center:location;
            if(!reuse){$('hint').textContent='Radio de '+radius+' m';status('Cargando lotes del radio…');}
            card.setAttribute('aria-busy','true');
            timer=setTimeout(()=>update(center,radius,epoch,areaController.signal),450);
        }
        $('close').addEventListener('click',()=>{card.hidden=true;streetFacade?.suspend();});
        $('toggle').addEventListener('click',()=>{
            const content=$('content'),toggle=$('toggle');content.hidden=!content.hidden;
            card.dataset.collapsed=String(content.hidden);
            toggle.setAttribute('aria-expanded',String(!content.hidden));
            toggle.setAttribute('aria-label',(content.hidden?'Expandir':'Colapsar')+' información catastral');
            toggle.textContent=content.hidden?'+':'−';
            if(content.hidden)streetFacade?.suspend();else if(target)streetFacade?.queue(target);
        });
        // Moving or closing the small card never changes the map or its lot layer.
        const host=document.getElementById('map-container'),handle=$('handle');let drag=null;
        function move(x,y){if(!host?.clientWidth)return;const bounds=window.ACMCardDock?.bounds()||{top:8,bottom:8};card.style.left=Math.max(8,Math.min(host.clientWidth-card.offsetWidth-8,x))+'px';card.style.top=Math.max(bounds.top,Math.min(host.clientHeight-card.offsetHeight-bounds.bottom,y))+'px';card.style.right='auto';card.style.bottom='auto';}
        handle.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('button')||card.classList.contains('cmp-map-docked'))return;e.preventDefault();const r=card.getBoundingClientRect(),h=host.getBoundingClientRect();drag={id:e.pointerId,x:e.clientX,y:e.clientY,left:r.left-h.left,top:r.top-h.top};handle.setPointerCapture(e.pointerId);});
        handle.addEventListener('pointermove',e=>{if(drag)move(drag.left+e.clientX-drag.x,drag.top+e.clientY-drag.y);});
        ['pointerup','pointercancel','lostpointercapture'].forEach(name=>handle.addEventListener(name,()=>{drag=null;}));
        handle.addEventListener('keydown',e=>{if(e.target!==handle||card.classList.contains('cmp-map-docked'))return;const shifts={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]},d=shifts[e.key];if(!d)return;e.preventDefault();const r=card.getBoundingClientRect(),h=host.getBoundingClientRect();move(r.left-h.left+d[0],r.top-h.top+d[1]);});
        document.addEventListener('acm:workspace-resize',()=>{if(card.hidden||card.classList.contains('cmp-map-docked')||!card.style.left)return;move(parseFloat(card.style.left),parseFloat(card.style.top));});
        document.addEventListener('acm:card-dock-layout',()=>{if(card.hidden||card.classList.contains('cmp-map-docked')||!card.style.left)return;move(parseFloat(card.style.left),parseFloat(card.style.top));});
        $('retry').addEventListener('click',()=>{if(target)queue(target,true);});
        $('report').addEventListener('change',()=>{if(!lot)return;const stamp=++serial;controller?.abort();controller=new AbortController();card.setAttribute('aria-busy','true');details(stamp,$('report').value);});
        document.addEventListener('acm:target-location',e=>queue(e.detail));
        document.addEventListener('acm:search-completed',e=>queue(e.detail));
        window.addEventListener?.('storage',event=>{
            if(event.key!=='catastro-source-placement'||!target)return;
            reloadGeometry();
        });
        window.addEventListener?.('focus',()=>checkRevision());
        document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(revisionTimer);revisionTimer=null;}else checkRevision();});
        const form=document.getElementById('cmp-form');
        ['lat','lng','radius'].forEach(k=>form.elements[k].addEventListener('change',()=>queue({lat:form.elements.lat.value,lng:form.elements.lng.value})));
        if(document.getElementById('cmp-role-analysis-data')||document.getElementById('cmp-replication-data'))queue({lat:form.elements.lat.value,lng:form.elements.lng.value});
    }
    window.ACMCadastral={init};
})();
